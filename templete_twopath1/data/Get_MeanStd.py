import os
import pdb
import numpy as np
import cv2

filepath =  '/home/shimy/FusionData/sptotal_mri/validation'  # 数据集目录
pathDir = os.listdir(filepath)

R_channel = 0
G_channel = 0
B_channel = 0
for idx in range(len(pathDir)):
    filename = pathDir[idx]
    img = cv2.imread(os.path.join(filepath, filename)) / 255.0
    # print(img.shape)
    R_channel = R_channel + np.sum(img[:, :, 0])
    G_channel = G_channel + np.sum(img[:, :, 1])
    B_channel = B_channel + np.sum(img[:, :, 2])

num = len(pathDir) * 180 * 180  # 这里（512,512）是每幅图片的大小，所有图片尺寸都一样
R_mean = R_channel / num
G_mean = G_channel / num
B_mean = B_channel / num

R_channel = 0
G_channel = 0
B_channel = 0
for idx in range(len(pathDir)):
    filename = pathDir[idx]
    img = cv2.imread(os.path.join(filepath, filename)) / 255.0
    R_channel = R_channel + np.sum((img[:, :, 0] - R_mean) ** 2)
    G_channel = G_channel + np.sum((img[:, :, 1] - G_mean) ** 2)
    B_channel = B_channel + np.sum((img[:, :, 2] - B_mean) ** 2)

R_var = np.sqrt(R_channel / num)
G_var = np.sqrt(G_channel / num)
B_var = np.sqrt(B_channel / num)
print("R_mean is %f, G_mean is %f, B_mean is %f" % (R_mean, G_mean, B_mean))
print("R_var is %f, G_var is %f, B_var is %f" % (R_var, G_var, B_var))