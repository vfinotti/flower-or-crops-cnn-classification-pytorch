# Flower or Crops CNN classification using Pytorch

### Overview
This repository contains the training/evaluation scripts for a Convolutional Neural Network made for detecting flowers in the middle of a plantation. The goal is to detect [_ipomoea grandifolia_](http://lmgtfy.com/?q=ipomoea+grandifolia), one of the weeds common in sugarcane plantations.

### CNN Architectures and framework
The idea is to reuse popular Imagenet architectures, fine-tuning them with a custom set of flower images (signal) and miscellaneous plantation images (background). The framework chosen for that is Pytorch. The trained architectures and their respective performance are listed bellow:

- VGG16
  - Accuracy: 0.9900
  - Model size: 512 MB
- Squeezenet 1.1
  - Accuracy: 0.9805
  - Model size: 2.8 MB
