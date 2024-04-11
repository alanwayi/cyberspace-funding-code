# 数据投毒攻击对联邦学习系统的影响

安装 创建一个虚拟环境（Python 3.7） 在虚拟环境中安装依赖项（pip install -r requirements.pip） 如果您计划使用防御功能，则需要安装 matplotlib。这不是运行实验所必需的，也不包括在 requirements 文件中。 执行说明 使用这个存储库，您可以复制 ESORICS 中展示的所有结果。我们下面概述了执行不同实验所需的步骤。

设置 在运行任何实验之前，您必须完成一些设置：

python3 generate_data_distribution.py：这将下载数据集，并生成训练和测试数据的静态分布，以保证实验的一致性。 python3 generate_default_models.py：这将生成论文中使用的所有模型的实例，并保存到磁盘上。 一般信息 一些提示和一般信息：

大多数超参数可以在 federated_learning/arguments.py 文件中设置。 大多数特定实验设置位于相应的实验文件中（请参阅下面的各个部分）。 实验 - 标签翻转攻击可行性 运行攻击：python3 label_flipping_attack.py

实验 - 标签翻转攻击的攻击时机 运行攻击：python3 attack_timing.py

实验 - 恶意参与者可用性 运行攻击：python3 malicious_participant_availability.py

实验 - 防御标签翻转攻击 运行防御：python3 defense.py

实验超参数 CIFAR10 的推荐默认超参数（使用提供的 CNN）：

批量大小：10 学习率（LR）：0.01 训练轮数：200 动量：0.5 调度器步长：50 调度器 gamma：0.5 最小学习率：1e-10 Fashion-MNIST 的推荐默认超参数（使用提供的 CNN）：

批量大小：4 学习率（LR）：0.001 训练轮数：200 动量：0.9 调度器步长：10 调度器 gamma：0.1 最小学习率：1e-10Citing
