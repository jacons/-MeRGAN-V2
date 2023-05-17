import torch
from torch import Tensor, zeros, full, cat, arange
from torch.utils.data import DataLoader

from Generator import Generator
from Utils import ExperienceDataset, generate_classes


class Join_replay:
    def __init__(self, generator: Generator, batch_size: int, buff_img: int, img_size: int,
                 device: str = "cpu"):

        self.g = generator
        self.img_size = img_size
        self.batch_size = batch_size
        self.buff_img = buff_img
        self.device = device

    def create_buffer(self,
                      id_exp: int,
                      usable_num: Tensor,
                      source: tuple[Tensor, Tensor]) -> DataLoader:

        real_image, real_label = source

        if id_exp == 0:  # No previous experience (first experience)
            return DataLoader(ExperienceDataset(real_image, real_label, self.device),
                              shuffle=True,
                              batch_size=self.batch_size)
        elif id_exp > 0:  # generating buffer replay

            device = self.device

            # Define the number of images to generate
            img_to_create = self.buff_img * usable_num.size(0)

            gen_buffer = zeros((img_to_create, 1, self.img_size, self.img_size))

            with torch.no_grad():
                generate_classes(self.g, usable_num.size(0), 10, "cuda")

                count = 0
                for i in usable_num:
                    to_generate = self.buff_img
                    while to_generate > 0:
                        batch_size = min(256, to_generate)
                        gen_label = full((batch_size,), i, device=device)
                        fake_img = self.g(gen_label)
                        gen_buffer[count:count + batch_size] = fake_img.cpu()

                        count += batch_size
                        to_generate -= batch_size

            custom_x = cat((real_image, gen_buffer), dim=0)
            custom_y = cat(
                (real_label, usable_num.repeat_interleave(self.buff_img)),
                dim=0)

            print("Buffer dimension", img_to_create)
            print("Total dataloader", custom_x.size(0))

            return DataLoader(ExperienceDataset(custom_x, custom_y, self.device),
                              shuffle=True,
                              batch_size=self.batch_size)
