> **University of Pisa** \
> **M.Sc. Computer Science, Artificial Intelligence** \
> **Continual learning 2022/23** \
> **Authors**

* Andrea Iommi - a.iommi2@studenti.unipi.it

# Memory Replay GANs

# Learning to generate images from new categories without forgetting

#### [(original paper)](https://proceedings.neurips.cc/paper/2018/hash/a57e8915461b83adefb011530b711704-Abstract.html)

### Notebooks

* Classical acGAN in offline settings
* Classical acGAN in online settings
* acGAN with join retrain
* acGAN with replay alignment

### 1) Introduction and problem settings

The aim of this small project is to have a deal with some Continual learning (CL) methods in the Axuliarity Conditional
Adversarial Networks (acGAN).
Typically, in a standard setting, we train a network passing the whole dataset at the same time, but this kind of
approach is not always possible: maybe all classes in the database are not available at the same time, the dataset is
extremely large and cannot suit in RAM or the environment provide us one class per time and for privacy setting the data
cannot be stored and so on.

The continual learning methods implemented give us a solution. More exactly, we explored the **join retrain** and the *
*replay alignment**.
The first one exploits a buffer to avoid that the network forgets the previous information acquired. The peculiarity is
that the buffer is non composed by the input taken from the previous experiences (in this case we are talking of images)
but are self generated by the network before starting the next experience.
Regarding the second method, it adopts a more implicit mechanism. It adds the "alignment" loss that aims to keep the
output of the network in the previous experience equal to the output of the network in the current one.

### 2) Tools

All implementations are preformed from scratch in pytorch. For the continual learning tools, the theory can be found in
the original papaer.

### 3) Model selection and hyperparameter

We tried different configurations of hyperparameter in order to choose the best ones. In particular:

|       	       |          	           | 	                                                                                                             | 	  |
|:-------------:|:--------------------:|---------------------------------------------------------------------------------------------------------------|----|
| num_classes 	 |     10         	     | 	                                                                                                             | 	  |
|  img_size  	  |     32         	     | 	                                                                                                             | 	  |
|  channels  	  |     1         	      | 	                                                                                                             | 	  |
|  n_epochs  	  |  30/50/**100**   	   | Under 30 there was under-fitting, and with 100 we obtained good results                                     	 | 	  |
| batch_size 	  |   **32**/64     	    | The original paper suggests 64, but with some experiments 32 seems more suitable                            	 | 	  |
| embeddings 	  |  **100**/150/200  	  | The results were very similarity, we think that is not so much crucial for this kind of purpose             	 | 	  |
|   lr     	    | **7e-5**/1e-4/1e-3 	 | (Also in this way the original paper suggests 1e-4 but since we've shrunk the batch_size, we reduced the lr 	 | 	  |

### 4) Conclusion