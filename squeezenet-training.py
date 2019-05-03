#!/usr/bin/env python3

# coding: utf-8

# Using the tutorial from https://www.kaggle.com/carloalbertobarbano/vgg16-transfer-learning-pytorch
# Since some images showed problems with the EXIF data, I followed the suggetion to delete this information: https://www.kaggle.com/c/intel-mobileodt-cervical-cancer-screening/discussion/31558
# Download the vgg16_bn file into the directory from the link: https://download.pytorch.org/models/squeezenet1_1-f364aa15.pth

# import warnings; warnings.simplefilter('ignore')

# import os
# os.environ['CUDA_DEVICE_ORDER']='PCI_BUS_ID'
# # The GPU id to use, usually either 0 or 1
# os.environ['CUDA_VISIBLE_DEVICES']='1'
#
# CUDA_DEVICE_ORDER='PCI_BUS_ID' CUDA_VISIBLE_DEVICES='1'


import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
from torch.autograd import Variable
import numpy as np
import torchvision
from torchvision import datasets, models, transforms
import matplotlib.pyplot as plt
import time
import os
import copy

# importing fixed version of squeezenet class and functions
import squeezenet_fix

plt.ion()

use_gpu = torch.cuda.is_available()
# use_gpu = False
if use_gpu:
    print("Using CUDA")


## DATA LOADER

data_dir = './images'
TRAIN = 'train'
VAL = 'val'
TEST = 'test'

# Squeezenet Takes 224x224 images as input, so we resize all of them
data_transforms = {
    TRAIN: transforms.Compose([
        # Data augmentation is a good practice for the train set
        # Here, we randomly crop the image to 224x224 and
        # randomly flip it horizontally.
        transforms.RandomResizedCrop(224),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
    ]),
    # VAL: transforms.Compose([
    #     transforms.Resize(256),
    #     transforms.CenterCrop(224),
    #     transforms.ToTensor(),
    # ]),
    TEST: transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
    ])
}

image_datasets = {
    x: datasets.ImageFolder(
        os.path.join(data_dir, x),
        transform=data_transforms[x]
    )
    for x in [TRAIN, TEST]
}

dataloaders = {
    x: torch.utils.data.DataLoader(
        image_datasets[x], batch_size=8,
        shuffle=True, num_workers=4
    )
    for x in [TRAIN, TEST]
}

dataset_sizes = {x: len(image_datasets[x]) for x in [TRAIN, TEST]}

for x in [TRAIN, TEST]:
    print("Loaded {} images under {}".format(dataset_sizes[x], x))

print("Classes: ")
class_names = image_datasets[TRAIN].classes
print(image_datasets[TRAIN].classes)


## UTILS


def imshow(inp, title=None):
    inp = inp.numpy().transpose((1, 2, 0))
    # plt.figure(figsize=(10, 10))
    plt.axis('off')
    plt.imshow(inp)
    if title is not None:
        plt.title(title)
    plt.pause(0.001)

def show_databatch(inputs, classes):
    out = torchvision.utils.make_grid(inputs)
    imshow(out, title=[class_names[x] for x in classes])

# Get a batch of training data
# inputs, classes = next(iter(dataloaders[TRAIN]))
# show_databatch(inputs, classes)

def visualize_model(squeezenet, num_images=6):
    was_training = squeezenet.training

    # Set model for evaluation
    squeezenet.train(False)
    squeezenet.eval()

    images_so_far = 0

    for i, data in enumerate(dataloaders[TEST]):
        inputs, labels = data
        size = inputs.size()[0]

        with torch.no_grad():
            if use_gpu:
                inputs, labels = inputs.cuda(), labels.cuda()
            else:
                inputs, labels = inputs, labels

                outputs = squeezenet(inputs)

                _, preds = torch.max(outputs.data, 1)
                predicted_labels = [preds[j] for j in range(inputs.size()[0])]

                print("Ground truth:")
                show_databatch(inputs.data.cpu(), labels.data.cpu())
                print("Prediction:")
                show_databatch(inputs.data.cpu(), predicted_labels)

        images_so_far += size
        if images_so_far >= num_images:
            break

    squeezenet.train(mode=was_training) # Revert model back to original training state

def eval_model(squeezenet, criterion):
    since = time.time()
    avg_loss = 0
    avg_acc = 0
    loss_test = 0
    acc_test = 0

    test_batches = len(dataloaders[TEST])
    print("Evaluating model")
    print('-' * 10)

    squeezenet.train(False)
    squeezenet.eval()

    with torch.no_grad():
        for i, data in enumerate(dataloaders[TEST]):
            if i % 10 == 0:
                print("\rTest batch {}/{}".format(i, test_batches), end='', flush=True)


            inputs, labels = data
            if use_gpu:
                inputs, labels = inputs.cuda(), labels.cuda()
            else:
                inputs, labels = inputs, labels

            outputs = squeezenet(inputs)

            _, preds = torch.max(outputs.data, 1)
            loss = criterion(outputs, labels)

            loss_test += loss.data
            acc_test += torch.sum(preds == labels.data).item()

            # del inputs, labels, outputs, preds
            # torch.cuda.empty_cache()

    avg_loss = loss_test / dataset_sizes[TEST]
    avg_acc = acc_test / dataset_sizes[TEST]

    elapsed_time = time.time() - since
    print()
    print("Evaluation completed in {:.0f}m {:.0f}s".format(elapsed_time // 60, elapsed_time % 60))
    print("Avg loss (test): {:.4f}".format(avg_loss))
    print("Avg acc (test): {:.4f}".format(avg_acc))
    print('-' * 10)


## MODEL CREATION

# Load the pretrained model from pytorch
# squeezenet1_1 = models.squeezenet1_1()
squeezenet1_1 = squeezenet_fix.squeezenet1_1()

squeezenet1_1.load_state_dict(torch.load("./weights/squeezenet1_1-f364aa15.pth"))
print(squeezenet1_1.classifier[1].out_channels) # 1000

#   (classifier): Sequential(
#     (0): Dropout(p=0.5)
#     (1): Conv2d(512, 1000, kernel_size=(1, 1), stride=(1, 1))
#     (2): ReLU(inplace)
#     (3): AdaptiveAvgPool2d(output_size=(1, 1))
#   )
# )


# Freeze training for all layers
for param in squeezenet1_1.features.parameters():
    param.require_grad = False

# Newly created modules have require_grad=True by default
num_features = squeezenet1_1.classifier[1].in_channels
features = list(squeezenet1_1.classifier.children())[:-3] # Remove last 3 layers
features.extend([nn.Conv2d(num_features, len(class_names), kernel_size=1)]) # Add
features.extend([nn.ReLU(inplace=True)]) # Add
features.extend([nn.AdaptiveAvgPool2d(output_size=(1,1))]) # Add
# features.extend([nn.Linear(num_features, len(class_names))]) # Add our layer with 2 outputs
# features.extend([nn.Linear(num_features, 1)]) # Add our layer with 1 output, '0' or '1'
squeezenet1_1.classifier = nn.Sequential(*features) # Replace the model classifier
print(squeezenet1_1)

# If you want to train the model for more than 2 epochs, set this to True after the first run
resume_training = False

if resume_training:
    print("Loading pretrained model..")
    squeezenet1_1.load_state_dict(torch.load('../weights/squeezenet_v1-flower-or-crops.pt'))
    print("Loaded!")

if use_gpu:
    squeezenet1_1.cuda() #.cuda() will move everything to the GPU side

criterion = nn.CrossEntropyLoss()

optimizer_ft = optim.SGD(squeezenet1_1.parameters(), lr=0.001, momentum=0.9)
exp_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=7, gamma=0.1)

print("Test before training")
eval_model(squeezenet1_1, criterion)


## TRAINING


def train_model(squeezenet, criterion, optimizer, scheduler, num_epochs=10):
    since = time.time()
    best_model_wts = copy.deepcopy(squeezenet.state_dict())
    best_acc = 0.0

    avg_loss = 0
    avg_acc = 0
    avg_loss_val = 0
    avg_acc_val = 0

    train_batches = len(dataloaders[TRAIN])
    val_batches = len(dataloaders[TEST])

    for epoch in range(num_epochs):
        print("Epoch {}/{}".format(epoch, num_epochs))
        print('-' * 10)

        loss_train = 0
        loss_val = 0
        acc_train = 0
        acc_val = 0

        squeezenet.train(True)

        for i, data in enumerate(dataloaders[TRAIN]):
            if i % 10 == 0:
                print("\rTraining batch {}/{}".format(i, train_batches / 2), end='', flush=True)

            # Use half training dataset
            if i >= train_batches / 2:
                break

            inputs, labels = data

            if use_gpu:
                inputs, labels = inputs.cuda(), labels.cuda()
            else:
                inputs, labels = inputs, labels

            optimizer.zero_grad()

            outputs = squeezenet(inputs)

            _, preds = torch.max(outputs.data, 1)
            loss = criterion(outputs, labels)

            loss.backward()
            optimizer.step()

            loss_train += loss.data
            acc_train += torch.sum(preds == labels.data).item()

            # del inputs, labels, outputs, preds
            # torch.cuda.empty_cache()

        print()
        # * 2 as we only used half of the dataset
        avg_loss = loss_train * 2 / dataset_sizes[TRAIN]
        avg_acc = acc_train * 2 / dataset_sizes[TRAIN]

        squeezenet.train(False)
        squeezenet.eval()

        for i, data in enumerate(dataloaders[TEST]):
            if i % 10 == 0:
                print("\rValidation batch {}/{}".format(i, val_batches), end='', flush=True)

            inputs, labels = data

            with torch.no_grad():
                if use_gpu:
                    inputs, labels = inputs.cuda(), labels.cuda()
                else:
                    inputs, labels = inputs, labels

                optimizer.zero_grad()

                outputs = squeezenet(inputs)

                _, preds = torch.max(outputs.data, 1)
                loss = criterion(outputs, labels)

                loss_val += loss.data
                acc_val += torch.sum(preds == labels.data).item()

                # del inputs, labels, outputs, preds
                # torch.cuda.empty_cache()

        avg_loss_val = loss_val / dataset_sizes[TEST]
        avg_acc_val = acc_val / dataset_sizes[TEST]

        print()
        print("Epoch {} result: ".format(epoch))
        print("Avg loss (train): {:.4f}".format(avg_loss))
        print("Avg acc (train): {:.4f}".format(avg_acc))
        print("Avg loss (val): {:.4f}".format(avg_loss_val))
        print("Avg acc (val): {:.4f}".format(avg_acc_val))
        print('-' * 10)
        print()

        if avg_acc_val > best_acc:
            best_acc = avg_acc_val
            best_model_wts = copy.deepcopy(squeezenet.state_dict())

    elapsed_time = time.time() - since
    print()
    print("Training completed in {:.0f}m {:.0f}s".format(elapsed_time // 60, elapsed_time % 60))
    print("Best acc: {:.4f}".format(best_acc))

    squeezenet.load_state_dict(best_model_wts)
    return squeezenet

squeezenet = train_model(squeezenet1_1, criterion, optimizer_ft, exp_lr_scheduler, num_epochs=2)
torch.save(squeezenet1_1.state_dict(), 'weights/squeezenet_v1-flower-or-crops.pt')
