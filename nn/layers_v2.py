# -*- coding: utf-8 -*-
"""
 @File    : layers_v2.py
 @Time    : 2020/4/25 上午9:15
 @Author  : yizuotian
 @Description    : v2版前向、反向计算；解决卷积计算速度慢的问题
"""
import time

import numpy as np


def _single_channel_conv_v1(z, K, b=0, padding=(0, 0)):
    """
    当通道卷积操作
    :param z: 卷积层矩阵
    :param K: 卷积核
    :param b: 偏置
    :param padding: padding
    :return: 卷积结果
    """
    padding_z = np.lib.pad(z, ((padding[0], padding[0]), (padding[1], padding[1])), 'constant', constant_values=0)
    height, width = padding_z.shape
    k1, k2 = K.shape
    conv_z = np.zeros((1 + (height - k1), 1 + (width - k2)))
    for h in np.arange(height - k1 + 1):
        for w in np.arange(width - k2 + 1):
            conv_z[h, w] = np.sum(padding_z[h:h + k1, w:w + k2] * K)
    return conv_z + b


def _single_channel_conv(z, K, b=0, padding=(0, 0)):
    """
    当通道卷积操作
    :param z: 卷积层矩阵
    :param K: 卷积核
    :param b: 偏置
    :param padding: padding
    :return: 卷积结果
    """
    padding_z = np.lib.pad(z, ((padding[0], padding[0]), (padding[1], padding[1])), 'constant', constant_values=0)
    height, width = padding_z.shape
    k1, k2 = K.shape
    oh, ow = (1 + (height - k1), 1 + (width - k2))  # 输出的高度和宽度
    conv_z = np.zeros((1 + (height - k1), 1 + (width - k2)))
    # 遍历卷积比遍历特征高效
    for i in range(k1):
        for j in range(k2):
            conv_z += padding_z[i:i + oh, j:j + ow] * K[i, j]

    return conv_z + b


def conv_forward_v1(z, K, b, padding=(0, 0)):
    """
    多通道卷积前向过程
    :param z: 卷积层矩阵,形状(N,C,H,W)，N为batch_size，C为通道数
    :param K: 卷积核,形状(C,D,k1,k2), C为输入通道数，D为输出通道数
    :param b: 偏置,形状(D,)
    :param padding: padding
    :return: conv_z: 卷积结果[N,D,oH,oW]
    """
    padding_z = np.lib.pad(z, ((0, 0), (0, 0), (padding[0], padding[0]), (padding[1], padding[1])), 'constant',
                           constant_values=0)
    N, _, height, width = padding_z.shape
    C, D, k1, k2 = K.shape
    oh, ow = (1 + (height - k1), 1 + (width - k2))  # 输出的高度和宽度
    conv_z = np.zeros((N, D, oh, ow))
    for n in np.arange(N):
        for d in np.arange(D):
            for h in np.arange(oh):
                for w in np.arange(oh):
                    conv_z[n, d, h, w] = np.sum(
                        padding_z[n, :, h:h + k1, w:w + k2] * K[:, d]) + b[d]
    return conv_z


def _conv_forward_old(z, K, b, padding=(0, 0)):
    """
    占用太多内存反而慢
    多通道卷积前向过程;
    :param z: 卷积层矩阵,形状(N,C,H,W)，N为batch_size，C为通道数
    :param K: 卷积核,形状(C,D,k1,k2), C为输入通道数，D为输出通道数
    :param b: 偏置,形状(D,)
    :param padding: padding
    :return: conv_z: 卷积结果[N,D,oH,oW]
    """
    padding_z = np.lib.pad(z, ((0, 0), (0, 0), (padding[0], padding[0]), (padding[1], padding[1])), 'constant',
                           constant_values=0)
    N, _, height, width = padding_z.shape
    C, D, k1, k2 = K.shape
    oh, ow = (1 + (height - k1), 1 + (width - k2))  # 输出的高度和宽度

    # 扩维
    padding_z = padding_z[:, :, np.newaxis, :, :]  # 扩维[N,C,1,H,W] 与K [C,D,K1,K2] 可以广播
    K = K[:, :, :, :, np.newaxis, np.newaxis]
    conv_z = np.zeros((N, C, D, oh, ow))

    # 批量卷积
    for i in range(k1):
        for j in range(k2):
            # [N,C,1,oh,ow]*[C,D,1,1] =>[N,C,D,oh,ow]
            conv_z += padding_z[:, :, :, i:i + oh, j:j + ow] * K[:, :, i, j]

    conv_z = np.sum(conv_z, axis=1)  # [N, C, D, oh, ow] => [N, D, oh, ow]
    # 增加偏置 [N, D, oh, ow]+[D, 1, 1]
    conv_z += b[:, np.newaxis, np.newaxis]
    return conv_z


def _conv_forward(z, K, b, padding=(0, 0)):
    """
    多通道卷积前向过程
    :param z: 卷积层矩阵,形状(N,C,H,W)，N为batch_size，C为通道数
    :param K: 卷积核,形状(C,D,k1,k2), C为输入通道数，D为输出通道数
    :param b: 偏置,形状(D,)
    :param padding: padding
    :return: conv_z: 卷积结果[N,D,oH,oW]
    """
    padding_z = np.lib.pad(z, ((0, 0), (0, 0), (padding[0], padding[0]), (padding[1], padding[1])), 'constant',
                           constant_values=0)
    N, _, height, width = padding_z.shape
    C, D, k1, k2 = K.shape
    oh, ow = (1 + (height - k1), 1 + (width - k2))  # 输出的高度和宽度

    # 扩维
    padding_z = padding_z[:, :, np.newaxis, :, :]  # 扩维[N,C,1,H,W] 与K [C,D,K1,K2] 可以广播
    K = K[:, :, :, :, np.newaxis, np.newaxis]
    conv_z = np.zeros((N, D, oh, ow))

    # 批量卷积
    for c in range(C):
        for i in range(k1):
            for j in range(k2):
                # [N,C,1,oh,ow]*[C,D,1,1] =>[N,C,D,oh,ow]
                conv_z += padding_z[:, c, :, i:i + oh, j:j + ow] * K[c, :, i, j]

    # 增加偏置 [N, D, oh, ow]+[D, 1, 1]
    conv_z += b[:, np.newaxis, np.newaxis]
    return conv_z


def conv_forward(z, K, b, padding=(0, 0), strides=(1, 1)):
    """
    多通道卷积前向过程
    :param z: 卷积层矩阵,形状(N,C,H,W)，N为batch_size，C为通道数
    :param K: 卷积核,形状(C,D,k1,k2), C为输入通道数，D为输出通道数
    :param b: 偏置,形状(D,)
    :param padding: padding
    :param strides: 步长
    :return: conv_z: 卷积结果[N,D,oH,oW]
    """
    # 长宽方向步长
    sh, sw = strides
    origin_conv_z = _conv_forward(z, K, b, padding)
    # 步长为1时的输出卷积尺寸
    N, D, oh, ow = origin_conv_z.shape
    if sh * sw == 1:
        return origin_conv_z
    # 高度方向步长大于1
    elif sw == 1:
        conv_z = np.zeros((N, D, oh // sh, ow))
        for i in range(oh // sh):
            conv_z[:, :, i, :] = origin_conv_z[:, :, i * sh, :]
        return conv_z
    # 宽度方向步长大于1
    elif sh == 1:
        conv_z = np.zeros((N, D, oh, ow // sw))
        for j in range(ow // sw):
            conv_z[:, :, :, j] = origin_conv_z[:, :, :, j * sw]
        return conv_z
    # 高度宽度方向步长都大于1
    else:
        conv_z = np.zeros((N, D, oh // sh, ow // sw))
        for i in range(oh // sh):
            for j in range(ow // sw):
                conv_z[:, :, i, j] = origin_conv_z[:, :, i*sh, j * sw]
        return conv_z


def test_single_conv():
    """
    两个卷积结果一样，速度相差百倍以上
    :return:
    """
    z = np.random.randn(224, 224)
    K = np.random.randn(3, 3)

    s = time.time()
    o1 = _single_channel_conv_v1(z, K)
    print("v1 耗时:{}".format(time.time() - s))
    s = time.time()
    o2 = _single_channel_conv(z, K)
    print("v2 耗时:{}".format(time.time() - s))

    print(np.allclose(o1, o2))


def test_conv():
    """
    两个卷积结果一样，速度相差几十倍
    :return:
    """
    z = np.random.randn(4, 3, 224, 224)
    K = np.random.randn(3, 64, 3, 3)
    b = np.random.randn(64)

    s = time.time()
    o1 = conv_forward_v1(z, K, b)
    print("v1 耗时:{}".format(time.time() - s))
    s = time.time()
    o2 = _conv_forward(z, K, b)
    print("v2 耗时:{}".format(time.time() - s))

    print(np.allclose(o1, o2))


if __name__ == '__main__':
    # test_single_conv()
    test_conv()
