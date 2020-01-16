#
# Copyright (c) 2019 Idiap Research Institute, http://www.idiap.ch/
# Written by Suraj Srinivas <suraj.srinivas@idiap.ch>
#

""" Compute saliency maps of images from dataset folder 
    and dump them in a results folder """

import torch

from torchvision import datasets, transforms, utils
import matplotlib.pyplot as plt
import os
import cv2

# Import saliency methods and models
from saliency.fullgrad import FullGrad
from saliency.simple_fullgrad import SimpleFullGrad
from models.vgg import *
from models.resnet import *
from misc_functions import *

import time
# PATH variables
PATH = os.path.dirname(os.path.abspath(__file__)) + '/'
dataset = PATH + 'dataset/'

batch_size = 4

cuda = torch.cuda.is_available()
device = torch.device("cuda" if cuda else "cpu")

# Dataset loader for sample images
sample_loader = torch.utils.data.DataLoader(
    datasets.ImageFolder(dataset, transform=transforms.Compose([
                       transforms.Resize((224,224)),
                       transforms.ToTensor(),
                       transforms.Normalize(mean = [0.485, 0.456, 0.406],
                                        std = [0.229, 0.224, 0.225])
                   ])),
    batch_size= batch_size, shuffle=False)

normalize = transforms.Normalize(mean = [0.485, 0.456, 0.406],
                                    std = [0.229, 0.224, 0.225])
unnormalize = NormalizeInverse(mean = [0.485, 0.456, 0.406],
                                 std = [0.229, 0.224, 0.225])


# uncomment to use VGG
# model = vgg16_bn(pretrained=True)
model = resnet18(pretrained=True).to(device)

# Initialize FullGrad objects
fullgrad = FullGrad(model)
simple_fullgrad = SimpleFullGrad(model)

save_path = PATH + 'results/'

# Found this function on stackoverflow 
# url: https://stackoverflow.com/questions/43386432/how-to-get-indexes-of-k-maximum-values-from-a-numpy-multidimensional-array
# Other approach: flatten --> max --> modulo row len om index te getten.
def k_largest_index_argsort(a, k):
    idx = np.argsort(a.ravel())[:-k-1:-1]
    return np.column_stack(np.unravel_index(idx, a.shape))

def k_smallest_index_argsort(img,k):
    """
        Given a batch of images a [batch_size x 1 x 244 x 244]
        sort and return the indices for the (244*244)-k most important pixels
    """
    idx = np.argsort(img.ravel())[::-1][k:]
    return np.column_stack(np.unravel_index(idx, img.shape))


def return_k_index_argsort(img,k, method):
    idx = np.argsort(img.ravel())
    if method == "roar":
        return np.column_stack(np.unravel_index(idx[:-k-1:-1], img.shape))
    elif method == "pp":
        return np.column_stack(np.unravel_index(idx[::-1][:k], img.shape))


def get_k_based_percentage(img, percentage):
    w, h = img.shape
    numb_pix = w*h
    return numb_pix * percentage

def calc_mean_channels(img):
    mean_r = torch.mean(img[0,:,:])
    mean_g = torch.mean(img[1,:,:])
    mean_b = torch.mean(img[2,:,:])

    return mean_r, mean_g, mean_b

def replace_pixels(img, idx, approach = 'zero'):
    if approach == 'zero':
        for x,y in idx:
            img[:,x,y] = 0
    elif approach == 'mean':
        mean_r, mean_g, mean_b = calc_mean_channels(img)
        for x,y in idx:
            img[0,x,y] = mean_r
            img[1,x,y] = mean_g
            img[2,x,y] = mean_b

    return img

def compute_saliency_and_save(method = "roar"):
    former_output, new_images, image_counter = [], [], 0

    image_counter = 0
    for batch_idx, (data, target) in enumerate(sample_loader):
        data, target = data.to(device).requires_grad_(), target.to(device)

        # Compute saliency maps for the input data.
        cam, output_model = fullgrad.saliency(data)
        former_output.append(output_model)
        total_pixels = 244*244
        # ==== ======
        # Create another function to create these Ks
        if method == "roar":
            #Ks_roar = [0.1,0.25,0.50,0.75, 0.90] # roar
            Ks_roar = [0.1]
            Ks = [round(k * total_pixels) for k in Ks_roar]
        elif method == "pp":
            Ks_pp = [0.1] #pixel perturbation
            Ks = [round(total_pixels -  (k * total_pixels)) for k in Ks_pp]
        # ==== ======
        for k_index, k in enumerate(Ks):
        # Find most important pixels and replace.
            for i in range(data.size(0)):
                sal_map = cam[i,:,:,:].squeeze()
                image = unnormalize(data[i,:,:,:])
                #if method == "roar":
                    #indexes = k_largest_index_argsort(sal_map.detach().numpy(), k = round((244*224)*k))
               # elif method == "pp":
                    #indexes = k_smallest_index_argsort(sal_map.detach().numpy(), k = round((244*224)-(244*224)*k))
                indexes = return_k_index_argsort(sal_map.detach().numpy(), k, method)
                new_image = replace_pixels(image, indexes, 'zero')
                new_images.append(new_image)

            # Unnormalize and save images with the found pixels changed.
            # new_image = unnormalize(new_image)
                if method == "roar":
                    #print(f'percentage of pixels{Ks_roar[k_index]*100}')
                    utils.save_image(new_image, f'pixels_removed/{method}/removal{Ks_roar[k_index]*100}%/img_id={image_counter}removal={Ks_roar[k_index]*100}%.jpeg')
                elif method == "pp":
                    #utils.save_image(new_image, f'pixels_removed/{method}/removal{Ks_pp[k_index]*100}%/img_id={image_counter}removal={Ks_pp[k_index]*100}%.jpeg')
                    utils.save_image(new_image, f'pixels_removed/{method}img_id={image_counter}removal={Ks_pp[k_index]*100}%.jpeg')

                image_counter += 1
            

    return 1,2
    #return former_output, new_images

def compute_pertubation():
    methods = "pp"
    #Ks = compute_ks(method)
    former_output, new_images = compute_saliency_and_save(method, k)

    # normalized_images = normalize(new_images)
    #new_model_output = model.forward(np.asarray(new_images).from_numpy())

    # Calculate rare shit
    #max_index = output_model.argmax()
    #diff = abs(new_model_output[max_index]-output_model[max_index]).sum()
    #print(diff)
    return None


if __name__ == "__main__":
    # Create folder to saliency maps
    import time
    start_time = time.time()
    create_folder(save_path)
    compute_saliency_and_save()
    #compute_pertubation()
    #images = compute_perturbation()
    #compute_roar()
    print('Saliency maps saved.')
    print("--- %s seconds ---" % (time.time() - start_time))

        
        




