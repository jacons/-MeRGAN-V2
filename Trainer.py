import copy
import os
from typing import Dict

from torch import arange, ones, zeros, randint, cat, tensor, stack, normal, Tensor, no_grad
from torch.nn import BCELoss, CrossEntropyLoss, MSELoss
from torch.optim import Adam
from torch.utils.data import DataLoader
from tqdm import tqdm

from Discriminator import Discriminator
from Generator import Generator
from Join_retrain import Join_replay
from Plot_functions import save_grid
from Utils import weights_init_normal, ExperienceDataset, compute_acc


class Trainer:
    def __init__(self, config: Dict, generator: Generator = None, discriminator: Discriminator = None):

        # Retrieve the parameters
        self.device, self.n_epochs = config["device"], config["n_epochs"]
        self.img_size, self.embedding_dim = config["img_size"], config["embedding"]
        self.channels, self.batch_size = config["channels"], config["batch_size"]

        # n_rows number of rows in the image of progression
        self.num_classes, self.n_rows = config["num_classes"], 5
        self.eval_noise = normal(0, 1, (self.n_rows, self.num_classes, self.embedding_dim), device=self.device)
        self.eval_label = arange(0, self.num_classes).to(self.device)

        # Define the generator and discriminator if they are not provided
        if generator is None or discriminator is None:

            self.generator = Generator(
                num_classes=config["num_classes"],
                embedding_dim=config["embedding"],
                channels=self.channels
            ).to(self.device)

            self.discriminator = Discriminator(
                classes=config["num_classes"],
                channels=self.channels,
            ).to(self.device)

            self.discriminator.apply(weights_init_normal)
            self.generator.apply(weights_init_normal)
        else:
            self.generator = generator.to(self.device)
            self.discriminator = discriminator.to(self.device)

        # Loss functions
        self.adversarial_loss = BCELoss().to(self.device)
        self.auxiliary_loss = CrossEntropyLoss().to(self.device)

        self.optimizer_g = Adam(self.generator.parameters(), lr=config["lr_g"], betas=(0.5, 0.999))
        self.optimizer_d = Adam(self.discriminator.parameters(), lr=config["lr_d"], betas=(0.5, 0.999))

    def fit_classic(self, experiences, create_gif: bool = False,
                    folder: str = "classical_acgan") -> Tensor:

        if create_gif:
            os.makedirs(folder, exist_ok=True)

        device, n_epochs, batch_size_ = self.device, self.n_epochs, self.batch_size
        history, current_classes = [], None

        const_gen, const_dis = 0.5, 0.25

        for idx, (numbers, x, y) in enumerate(experiences):

            # Number that can be generated, because the model have seen
            current_classes = tensor(numbers)
            print("Experience -- ", idx + 1, "numbers", current_classes.tolist())

            loader = DataLoader(ExperienceDataset(x, y, device), shuffle=True, batch_size=batch_size_)
            for epoch in arange(0, n_epochs):
                for batch, (real_image, real_label) in enumerate(tqdm(loader)):
                    batch_size = real_image.size(0)

                    valid = ones((batch_size, 1), device=device)
                    fake = zeros((batch_size, 1), device=device)

                    # ---- Generator ----
                    self.optimizer_g.zero_grad()

                    gen_label = current_classes[randint(0, len(current_classes), size=(batch_size,))].to(device)
                    fake_img = self.generator(gen_label)

                    dis_output, aux_output = self.discriminator(fake_img)
                    errG = const_gen * (
                            self.adversarial_loss(dis_output, valid) +
                            self.auxiliary_loss(aux_output, gen_label))

                    errG.backward()
                    self.optimizer_g.step()

                    # ---- Discriminator ----
                    self.optimizer_d.zero_grad()

                    dis_real, aux_real = self.discriminator(real_image)
                    dis_fake, aux_fake = self.discriminator(fake_img.detach())

                    errD = const_dis * (
                            self.adversarial_loss(dis_real, valid) +
                            self.adversarial_loss(dis_fake, fake) +
                            self.auxiliary_loss(aux_real, real_label) +
                            self.auxiliary_loss(aux_fake, gen_label)
                    )

                    d_acc = compute_acc(
                        cat([aux_real, aux_fake], dim=0),
                        cat([real_label, gen_label], dim=0)
                    )

                    errD.backward()
                    self.optimizer_d.step()

                    history.append(tensor([errD.item(), errG.item(), d_acc]))

                    if create_gif and batch % 100 == 0:
                        self.save_progress(f"{folder}/img_{idx}_{epoch}_{batch}.png")

                print("[%d/%d] Loss_D: %.4f Loss_G: %.4f Acc %.6f"
                      % (epoch + 1, n_epochs, history[-1][0], history[-1][1],
                         history[-1][2]))

        return stack(history).T

    def fit_join_retrain(self, experiences, buff_img: int, create_gif: bool = False,
                         folder: str = "join_retrain") -> Tensor:

        if create_gif:
            os.makedirs(folder, exist_ok=True)

        device, n_epochs = self.device, self.n_epochs
        history, current_classes = [], None

        const_gen, const_dis = 0.5, 0.25

        jr = Join_replay(generator=self.generator,
                         batch_size=self.batch_size,
                         buff_img=buff_img,
                         img_size=self.img_size,
                         channels=self.channels,
                         device=device)

        for idx, (classes, x, y) in enumerate(experiences):

            loader = jr.create_buffer(idx, current_classes, (x, y))

            # Number that can be generated, because the model have seen
            new_classes = tensor(classes)
            current_classes = new_classes if current_classes is None else cat((current_classes, new_classes))
            print("Experience -- ", idx + 1, "numbers", current_classes.tolist())

            for epoch in arange(0, n_epochs):
                for batch, (real_image, real_label) in enumerate(tqdm(loader)):
                    batch_size = real_image.size(0)

                    valid, fake = ones((batch_size, 1), device=device), zeros((batch_size, 1), device=device)

                    # ---- Generator ----
                    self.optimizer_g.zero_grad()

                    gen_label = current_classes[randint(0, len(current_classes), size=(batch_size,))].to(device)
                    fake_img = self.generator(gen_label)

                    dis_output, aux_output = self.discriminator(fake_img)
                    errG = const_gen * (
                            self.adversarial_loss(dis_output, valid) +
                            self.auxiliary_loss(aux_output, gen_label))

                    errG.backward()
                    self.optimizer_g.step()

                    # ---- Discriminator ----
                    self.optimizer_d.zero_grad()

                    dis_real, aux_real = self.discriminator(real_image)
                    dis_fake, aux_fake = self.discriminator(fake_img.detach())

                    errD = const_dis * (
                            self.adversarial_loss(dis_real, valid) +
                            self.adversarial_loss(dis_fake, fake) +
                            self.auxiliary_loss(aux_real, real_label) +
                            self.auxiliary_loss(aux_fake, gen_label)
                    )

                    d_acc = compute_acc(
                        cat([aux_real, aux_fake], dim=0),
                        cat([real_label, gen_label], dim=0)
                    )

                    errD.backward()
                    self.optimizer_d.step()

                    history.append(tensor([errD.item(), errG.item(), d_acc]))

                    if create_gif and batch % 100 == 0:
                        self.save_progress(f"{folder}/img_{idx}_{epoch}_{batch}.png")

                print("[%d/%d] Loss_D: %.4f Loss_G: %.4f Acc %.6f"
                      % (epoch + 1, n_epochs, history[-1][0], history[-1][1],
                         history[-1][2]))

        return stack(history).T

    def fit_replay_alignment(self, experiences, create_gif: bool = False,
                             folder: str = "replay_alignment"):
        if create_gif:
            os.makedirs(folder, exist_ok=True)

        device, n_epochs, batch_size_ = self.device, self.n_epochs, self.batch_size
        history, current_classes = [], None

        const_gen, const_dis, const_ra = 0.5, 0.25, 1

        prev_gen, prev_classes = None, None
        alignment_loss = MSELoss().to(self.device)

        for idx, (classes, x, y) in enumerate(experiences):

            if idx > 0 and prev_classes is None:
                prev_classes = current_classes
            elif prev_classes is not None and idx > 0:
                prev_classes = cat((prev_classes, current_classes))

            current_classes = tensor(classes)  # Number that can be generated

            print("Experience -- ", idx + 1, "numbers", current_classes.tolist())
            if prev_classes is not None:
                print("Past experiences", prev_classes.tolist())

            loader = DataLoader(ExperienceDataset(x, y, device), shuffle=True, batch_size=batch_size_)
            for epoch in arange(0, n_epochs):
                for batch, (real_image, real_label) in enumerate(tqdm(loader)):
                    batch_size = real_image.size(0)

                    valid, fake = ones((batch_size, 1), device=device), zeros((batch_size, 1), device=device)

                    # ---- Generator ----
                    self.optimizer_g.zero_grad()

                    gen_label = current_classes[randint(0, len(current_classes), size=(batch_size,))].to(device)
                    fake_img = self.generator(gen_label)

                    dis_output, aux_output = self.discriminator(fake_img)

                    # replay alignment
                    align_loss = 0
                    if prev_gen is not None:
                        z = normal(0, 1, (batch_size_, self.embedding_dim), device=device)
                        gen_label_ = prev_classes[randint(0, len(prev_classes), size=(batch_size_,))].to(device)

                        fake_img1 = self.generator(gen_label_, z)
                        with no_grad():
                            fake_img2 = prev_gen(gen_label_, z)

                        align_loss = alignment_loss(fake_img1, fake_img2)

                    errG = const_gen * (
                            self.adversarial_loss(dis_output, valid) +
                            self.auxiliary_loss(aux_output, gen_label)
                    ) + const_ra * align_loss

                    errG.backward()
                    self.optimizer_g.step()

                    # ---- Discriminator ----
                    self.optimizer_d.zero_grad()

                    dis_real, aux_real = self.discriminator(real_image)
                    dis_fake, aux_fake = self.discriminator(fake_img.detach())

                    errD = const_dis * (
                            self.adversarial_loss(dis_real, valid) +
                            self.adversarial_loss(dis_fake, fake) +
                            self.auxiliary_loss(aux_real, real_label) +
                            self.auxiliary_loss(aux_fake, gen_label)
                    )

                    d_acc = compute_acc(
                        cat([aux_real, aux_fake], dim=0),
                        cat([real_label, gen_label], dim=0)
                    )

                    errD.backward()
                    self.optimizer_d.step()

                    history.append(tensor([errD.item(), errG.item(), d_acc]))

                    if create_gif and batch % 100 == 0:
                        self.save_progress(f"{folder}/img_{idx}_{epoch}_{batch}.png")

                print("[%d/%d] Loss_D: %.4f Loss_G: %.4f Acc %.6f"
                      % (epoch + 1, n_epochs, history[-1][0], history[-1][1],
                         history[-1][2]))

            prev_gen = copy.deepcopy(self.generator)

        return stack(history).T

    def save_progress(self, id_img: str):
        img = zeros((self.n_rows, self.num_classes, self.channels, self.img_size, self.img_size))
        with no_grad():
            for i in range(self.n_rows):
                img[i].copy_(self.generator(self.eval_label, self.eval_noise[i]))
        save_grid(img, self.n_rows, id_img)
