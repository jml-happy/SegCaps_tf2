'''
This program includes all functions of 2D color image processing for UNet, tiramisu, Capsule Nets (capsbasic) or SegCaps(segcapsr1 or segcapsr3).

@author: Cheng-Lin Li a.k.a. Clark

@copyright:  2018 Cheng-Lin Li@Insight AI. All rights reserved.

@license:    Licensed under the Apache License v2.0. http://www.apache.org/licenses/

@contact:    clark.cl.li@gmail.com

Tasks:
    The program based on parameters from main.py to load 2D color image files from folders.

    The program will convert all image files into numpy format then store training/testing images into 
    ./data/np_files and training (and testing) file lists under ./data/split_list folders. 
    You need to remove these two folders every time if you want to replace your training image and mask files. 
    The program will only read data from np_files folders.
    
Data:
    MS COCO 2017 or LUNA 2016 were tested on this package.
    You can leverage your own data set but the mask images should follow the format of MS COCO or with background color = 0 on each channel.
    

Features: 
    1. Integrated with MS COCO 2017 dataset.
    2. Use PILLOW library instead of SimpleITK for better support on RasberryPi
    3. add new generate_test_image function to process single image frame for video stream
'''

from __future__ import print_function
# import threading
import logging
from os.path import join, basename
from os import makedirs

import numpy as np
from numpy.random import rand, shuffle
from PIL import Image

# import matplotlib
# matplotlib.use('Agg')
import matplotlib.pyplot as plt


plt.ioff()

from utils.custom_data_aug import augmentImages, convert_img_data, convert_mask_data
from utils.threadsafe import threadsafe_generator

debug = True    
    
def convert_data_to_numpy(root_path, img_name, no_masks=False, overwrite=False):
    fname = img_name[:-4]
    numpy_path = join(root_path, 'np_files')
    img_path = join(root_path, 'imgs')
    mask_path = join(root_path, 'masks')
    fig_path = join(root_path, 'figs')
    try:
        makedirs(numpy_path)
    except:
        pass
    try:
        makedirs(fig_path)
    except:
        pass

    if not overwrite:
        try:
            with np.load(join(numpy_path, fname + '.npz')) as data:
                return data['img'], data['mask']
        except:
            pass

    try:       
        img = np.array(Image.open(join(img_path, img_name)))
        # Conver image to 3 dimensions
        img = convert_img_data(img, 3)
            
        if not no_masks:
            # Replace SimpleITK to PILLOW for 2D image support on Raspberry Pi
            mask = np.array(Image.open(join(mask_path, img_name))) # (x,y,4)
            
            mask = convert_mask_data(mask)

        if not no_masks:
            np.savez_compressed(join(numpy_path, fname + '.npz'), img=img, mask=mask)
        else:
            np.savez_compressed(join(numpy_path, fname + '.npz'), img=img)

        if not no_masks:
            return img, mask
        else:
            return img

    except Exception as e:
        print('\n'+'-'*100)
        print('Unable to load img or masks for {}'.format(fname))
        print(e)
        print('Skipping file')
        print('-'*100+'\n')

        return np.zeros(1), np.zeros(1)


def get_slice(image_data):
    return image_data[2]

@threadsafe_generator
def generate_train_batches(root_path, train_list, net_input_shape, net, batchSize=1, numSlices=1, subSampAmt=-1,
                           stride=1, downSampAmt=1, shuff=1, aug_data=1):
    # Create placeholders for training
    # (img_shape[1], img_shape[2], args.slices)
    print(f"\n\nTRAIN: net_input_shape: {net_input_shape}, net: {net}")
    logging.info('\n2d_generate_train_batches')

    img_batch = np.zeros((np.concatenate(((batchSize,), net_input_shape))), dtype=np.float32)
    # mask_batch = np.zeros((np.concatenate(((batchSize,), net_input_shape))), dtype=np.float32)
    mask_batch = np.zeros((np.concatenate(((batchSize,), (net_input_shape[0], net_input_shape[1], 1)))), dtype=np.uint8)
    print(f"TRAIN: img_batch shape: {img_batch.shape}, net: {net}")
    print(f"TRAIN: mask_batch shape: {mask_batch.shape}, net: {net}")
    print("TRAIN GEN: img_batch.ndim: ", img_batch.ndim)
    print("TRAIN GEN: mask_batch.ndim: ", mask_batch.ndim)
    train_printed_yield_shape_once = False
    while True:
        if shuff:
            shuffle(train_list)
        count = 0
        for i, scan_name in enumerate(train_list):
            try:
                # Read image file from pre-processing image numpy format compression files.
                scan_name = scan_name[0]
                path_to_np = join(root_path,'np_files',basename(scan_name)[:-3]+'npz')
                logging.info('\npath_to_np=%s'%(path_to_np))
                with np.load(path_to_np) as data:
                    train_img = data['img']
                    train_mask = data['mask']
            except:
                logging.info('\nPre-made numpy array not found for {}.\nCreating now...'.format(scan_name[:-4]))
                train_img, train_mask = convert_data_to_numpy(root_path, scan_name)
                if np.array_equal(train_img,np.zeros(1)):
                    continue
                else:
                    logging.info('\nFinished making npz file.')

            if numSlices == 1:
                subSampAmt = 0
            elif subSampAmt == -1 and numSlices > 1: # Only one slices. code can be removed.
                np.random.seed(None)
                subSampAmt = int(rand(1)*(train_img.shape[2]*0.05))
            # We don't need indicies in 2D image.  # ?????????????????
            indicies = np.arange(0, train_img.shape[2] - numSlices * (subSampAmt + 1) + 1, stride)
            if shuff:
                shuffle(indicies)

            for j in indicies:

                if not np.any(train_mask[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]):
                    continue
                # print("\nIn generator:")
                # print("len(input[img_batch): ", len(img_batch))
                # print("len(input[img_batch[0,:]): ", len(img_batch[0,:]))
                # print("len(input[img_batch[0,0,:]): ", len(img_batch[0,0,:]))
                # print("len(input[img_batch[0,0,0,:]): ", len(img_batch[0,0,0,:]))

                # print("\n")

                # print("len(input[mask_batch): ", len(mask_batch))
                # print("len(input[mask_batch[0,:]): ", len(mask_batch[0,:]))
                # print("len(input[mask_batch[0,0,:]): ", len(mask_batch[0,0,:]))
                # print("len(input[mask_batch[0,0,0,:]): ", len(mask_batch[0,0,0,:]))
                #####  THIS IS FOR 2D (IMAGE) DATA #####
                if img_batch.ndim == 4:
                    img_batch[count, :, :, :] = train_img[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
                    mask_batch[count, :, :, :] = train_mask[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]

                #####  THIS IS FOR 3D (CAT SCAN) DATA #####
                elif img_batch.ndim == 5:
                    # Assumes img and mask are single channel. Replace 0 with : if multi-channel.
                    img_batch[count, :, :, :, 0] = train_img[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
                    mask_batch[count, :, :, :, 0] = train_mask[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
                else:
                    logging.error('\nError this function currently only supports 2D and 3D data.')
                    exit(0)


                # print("TRAIN GEN LOOP: img_batch.shape: ", img_batch.shape)
                # print("TRAIN GEN LOOP: mask_batch.shape: ", mask_batch.shape)
                count += 1
                if count % batchSize == 0:
                    count = 0
                    if aug_data:
                        img_batch, mask_batch = augmentImages(img_batch, mask_batch)
                    if debug:
                    ######### SAVE THE IMAGE + MASK
                    #####  THIS IS FOR 2D (IMAGE) DATA #####
                        if img_batch.ndim == 4:
                            plt.imshow(np.squeeze(img_batch[0, :, :, 0]), cmap='gray')
                            plt.imshow(np.squeeze(mask_batch[0, :, :, 0]), alpha=0.15)

                    #####  THIS IS FOR 3D (CAT SCAN) DATA #####
                        elif img_batch.ndim == 5:
                            plt.imshow(np.squeeze(img_batch[0, :, :, 0, 0]), cmap='gray')
                            plt.imshow(np.squeeze(mask_batch[0, :, :, 0, 0]), alpha=0.15)
                        plt.savefig(join(root_path, 'logs', 'ex_train-combined.png'), format='png', bbox_inches='tight')
                        plt.close()

                    ######### SAVE THE IMAGE
                    #####  THIS IS FOR 2D (IMAGE) DATA #####
                        if img_batch.ndim == 4:
                            plt.imshow(np.squeeze(img_batch[0, :, :, 0]), cmap='gray')

                    #####  THIS IS FOR 3D (CAT SCAN) DATA #####
                        elif img_batch.ndim == 5:
                            plt.imshow(np.squeeze(img_batch[0, :, :, 0, 0]), cmap='gray')
                        plt.savefig(join(root_path, 'logs', 'ex_train-image.png'), format='png', bbox_inches='tight')
                        plt.close()

                    ######### SAVE THE  MASK
                    #####  THIS IS FOR 2D (IMAGE) DATA #####
                        if img_batch.ndim == 4:
                            plt.imshow(np.squeeze(mask_batch[0, :, :, 0]), alpha=0.15)

                    #####  THIS IS FOR 3D (CAT SCAN) DATA #####
                        elif img_batch.ndim == 5:
                            plt.imshow(np.squeeze(mask_batch[0, :, :, 0, 0]), alpha=0.15)
                        plt.savefig(join(root_path, 'logs', 'ex_train-mask.png'), format='png', bbox_inches='tight')
                        plt.close()

                    if net.find('caps') != -1: # if the network is capsule/segcaps structure
                        # [(1, 512, 512, 3), (1, 512, 512, 1)], [(1, 512, 512, 1), (1, 512, 512, 3)]
                        # or [(1, 512, 512, 3), (1, 512, 512, 3)], [(1, 512, 512, 3), (1, 512, 512, 3)]
                        # print("Inside the indice loop!")
                        if not train_printed_yield_shape_once:
                            print("TRAIN GEN LOOP YIELD: img_batch.shape: ", img_batch.shape)
                            print("TRAIN GEN LOOP YIELD: mask_batch.shape: ", mask_batch.shape)
                            train_printed_yield_shape_once = True
                        yield ([img_batch, mask_batch], [mask_batch, mask_batch*img_batch])
                    else:
                        yield (img_batch, mask_batch)

        if count != 0:
            if aug_data:
                img_batch[:count,...], mask_batch[:count,...] = augmentImages(img_batch[:count,...],
                                                                              mask_batch[:count,...])
            if net.find('caps') != -1:
                print("Inside the bottom part")
                yield ([img_batch[:count, ...], mask_batch[:count, ...]],
                       [mask_batch[:count, ...], mask_batch[:count, ...] * img_batch[:count, ...]])
            else:
                yield (img_batch[:count,...], mask_batch[:count,...])

@threadsafe_generator
def generate_val_batches(root_path, val_list, net_input_shape, net, batchSize=1, numSlices=1, subSampAmt=-1,
                         stride=1, downSampAmt=1, shuff=1):
    print(f"\nVALID GEN: net_input_shape: {net_input_shape}, net: {net}")
    logging.info('2d_generate_val_batches')
    # Create placeholders for validation
    img_batch = np.zeros((np.concatenate(((batchSize,), net_input_shape))), dtype=np.float32)
    # mask_batch = np.zeros((np.concatenate(((batchSize,), net_input_shape))), dtype=np.uint8)  ## originally this
    # THIS FORECES MASKS TO BE CREYSCALE
    # 3-channel masks cause crash, even with all GREYSCALE constants set False.
    mask_batch = np.zeros((np.concatenate(((batchSize,), (net_input_shape[0], net_input_shape[1], 1)))), dtype=np.uint8)  ## changed to this to match train
    
    print(f"TRAIN: img_batch shape: {img_batch.shape}, net: {net}")
    print(f"TRAIN: mask_batch shape: {mask_batch.shape}, net: {net}")
    print("VALID GEN: img_batch.ndim: ", img_batch.ndim)
    print("VALID GEN: mask_batch.ndim: ", mask_batch.ndim)
    val_printed_yield_shape_once = False
    while True:
        if shuff:
            shuffle(val_list)
        count = 0
        for i, scan_name in enumerate(val_list):
            try:
                scan_name = scan_name[0]
                path_to_np = join(root_path,'np_files',basename(scan_name)[:-3]+'npz')
                with np.load(path_to_np) as data:
                    val_img = data['img']
                    val_mask = data['mask']
            except:
                logging.info('\nPre-made numpy array not found for {}.\nCreating now...'.format(scan_name[:-4]))
                val_img, val_mask = convert_data_to_numpy(root_path, scan_name)
                if np.array_equal(val_img,np.zeros(1)):
                    continue
                else:
                    logging.info('\nFinished making npz file.')
            
            # New added for debugging
            if numSlices == 1:
                subSampAmt = 0
            elif subSampAmt == -1 and numSlices > 1: # Only one slices. code can be removed.
                np.random.seed(None)
                subSampAmt = int(rand(1)*(val_img.shape[2]*0.05))
            
            # We don't need indicies in 2D image.        
            indicies = np.arange(0, val_img.shape[2] - numSlices * (subSampAmt + 1) + 1, stride)
            if shuff:
                shuffle(indicies)

            for j in indicies:
                if not np.any(val_mask[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]):
                    continue
                if img_batch.ndim == 4:
                    img_batch[count, :, :, :] = val_img[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
                    mask_batch[count, :, :, :] = val_mask[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
                elif img_batch.ndim == 5:
                    # Assumes img and mask are single channel. Replace 0 with : if multi-channel.
                    img_batch[count, :, :, :, 0] = val_img[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
                    mask_batch[count, :, :, :, 0] = val_mask[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
                else:
                    logging.error('\nError this function currently only supports 2D and 3D data.')
                    exit(0)

                # print("VALID GEN LOOP: img_batch.shape: ", img_batch.shape)
                # print("VALID GEN LOOP: mask_batch.shape: ", mask_batch.shape)
                count += 1
                if count % batchSize == 0:
                    count = 0
                    if net.find('caps') != -1:
                        if not val_printed_yield_shape_once:
                            print("VAL GEN LOOP YIELD: img_batch.shape: ", img_batch.shape)
                            print("VAL GEN LOOP YIELD: mask_batch.shape: ", mask_batch.shape)
                            val_printed_yield_shape_once = True
                        yield ([img_batch, mask_batch], [mask_batch, mask_batch * img_batch])
                    else:
                        yield (img_batch, mask_batch)

        if count != 0:
            if net.find('caps') != -1:
                yield ([img_batch[:count, ...], mask_batch[:count, ...]],
                       [mask_batch[:count, ...], mask_batch[:count, ...] * img_batch[:count, ...]])
            else:
                yield (img_batch[:count,...], mask_batch[:count,...])

@threadsafe_generator
def generate_test_batches(root_path, test_list, net_input_shape, batchSize=1, numSlices=1, subSampAmt=0,
                          stride=1, downSampAmt=1):
    # Create placeholders for testing
    print(f"\nTEST GEN: net_input_shape: {net_input_shape}, net: <not a param>")
    logging.info('\nload_2D_data.generate_test_batches')
    img_batch = np.zeros((np.concatenate(((batchSize,), net_input_shape))), dtype=np.float32)
    count = 0
    logging.info('\nload_2D_data.generate_test_batches: test_list=%s'%(test_list))
    test_printed_yield_shape_once = False
    for i, scan_name in enumerate(test_list):
        try:
            scan_name = scan_name[0]
            path_to_np = join(root_path,'np_files',basename(scan_name)[:-3]+'npz')
            with np.load(path_to_np) as data:
                test_img = data['img'] # (512, 512, 1)
        except:
            logging.info('\nPre-made numpy array not found for {}.\nCreating now...'.format(scan_name[:-4]))
            test_img = convert_data_to_numpy(root_path, scan_name, no_masks=True)
            if np.array_equal(test_img,np.zeros(1)):
                continue
            else:
                logging.info('\nFinished making npz file.')

        indicies = np.arange(0, test_img.shape[2] - numSlices * (subSampAmt + 1) + 1, stride)
        for j in indicies:
            if img_batch.ndim == 4: 
                # (1, 512, 512, 1)
                img_batch[count, :, :, :] = test_img[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
            elif img_batch.ndim == 5:
                # Assumes img and mask are single channel. Replace 0 with : if multi-channel.
                img_batch[count, :, :, :, 0] = test_img[:, :, j:j + numSlices * (subSampAmt+1):subSampAmt+1]
            else:
                logging.error('\nError this function currently only supports 2D and 3D data.')
                exit(0)

            # print("TEST GEN LOOP: img_batch.shape: ", img_batch.shape)
            count += 1
            if count % batchSize == 0:
                count = 0
                if not test_printed_yield_shape_once:
                    print("TEST GEN LOOP YIELD: img_batch.shape: ", img_batch.shape)
                    test_printed_yield_shape_once = True
                yield (img_batch) 

    if count != 0:
        yield (img_batch[:count,:,:,:])
 
@threadsafe_generator
def generate_test_image(test_img, net_input_shape, batchSize=1, numSlices=1, subSampAmt=0,
                          stride=1, downSampAmt=1):
    '''
    test_img: numpy.array of image data, (height, width, channels)
    
    '''
    # Create placeholders for testing
    logging.info('\nload_2D_data.generate_test_image')
    # Convert image to 4 dimensions
    test_img = convert_img_data(test_img, 4)
        
    yield (test_img)
