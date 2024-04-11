# 标签反转攻击

## 先决条件

安装 Python 3.8 和 PyTorch 1.7.0+

## 数据集设置

### 数据集下载

将以下数据集下载到 './Code/datasets' 文件夹中。

CINIC-10 [1]

Yahoo 回答数据集:

https://www.kaggle.com/soumikrakshit/yahoo-answers-dataset

Criteo 数据集:

https://labs.criteo.com/2014/02/download-kaggle-display-advertising-challenge-dataset/

乳腺组织病理学图像：

https://www.kaggle.com/paultimothymooney/breasthistopathology-images

Tiny ImageNet:

https://www.kaggle.com/c/tiny-imagenet

乳腺癌威斯康星数据集：

https://archive.ics.uci.edu/ml/datasets/Breast+Cancer+Wisconsin+(Diagnostic)

CIFAR-10 或 CIFAR-100:

使用 PyTorch 内置的数据集类。

### 数据集预处理

使用 './Code/datasets_preprocess' 文件夹中的脚本对数据集进行预处理。

## 快速开始

### 对于 Windows 操作系统

使用 './Code' 文件夹中的批处理文件。

'run_training.bat': 训练模拟的 VFL 模型。

'run_model_completion.bat': 运行被动和主动标签推断攻击。

'run_direct_attack.bat': 运行直接标签推断攻击。

'run_training_possible_defense.bat': 测试针对被动和主动标签推断攻击的可能防御方法。

'run_direct_attack_possible_defense.bat': 测试针对直接标签推断攻击的可能防御方法。

### 对于 Linux 操作系统

使用批处理文件中的命令，例如，使用 'run_training.bat' 中的命令训练模拟的 VFL 模型。
