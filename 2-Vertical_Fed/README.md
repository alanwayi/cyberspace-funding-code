# 用Python实现纵向联邦分类任务

代码运行需要首先安装[Python](https://www.anaconda.com/products/individual)、[Pytorch](https://pytorch.org/get-started/locally/)环境。

在本目录下，在命令行中执行下面的命令：

python main.py

- 这段代码实现了一个垂直联邦学习的分布式逻辑回归算法，涉及三个客户端 `ClientA`、`ClientB` 和 `ClientC`，它们之间通过定义的通信方法实现数据交互和模型参数更新。

  这里是对代码中的主要部分进行解释：

  1. **Client 类**：
     - `Client` 类是所有客户端类的基类，定义了连接其他客户端和发送数据的基本功能。
  2. **ClientA 类**：
     - `ClientA` 类是一个客户端，负责处理部分数据 `XA` 和相关的模型参数更新。
     - `compute_z_a()` 方法计算 `XA` 的线性组合结果 `z_a`。
     - `compute_encrypted_dJ_a()` 方法计算加密梯度。
     - `task_1()`、`task_2()` 和 `task_3()` 方法分别表示 ClientA 在不同步骤中的任务执行流程，包括数据处理、加密通信和模型参数更新。
  3. **ClientB 类**：
     - `ClientB` 类类似于 `ClientA`，但处理不同的数据 `XB` 和 `y`，执行类似的任务流程。
  4. **ClientC 类**：
     - `ClientC` 类充当可信的第三方，负责生成和分发加密密钥，并协调 ClientA 和 ClientB 之间的通信。
  5. **load_data() 函数**：
     - `load_data()` 函数加载乳腺癌数据集并对其进行拆分和标准化。
  6. **vertically_partition_data() 函数**：
     - `vertically_partition_data()` 函数将数据按垂直分区分配给 ClientA 和 ClientB。
  7. **vertical_logistic_regression() 函数**：
     - `vertical_logistic_regression()` 函数定义了整个垂直联邦学习过程的执行流程，包括数据加载、初始化客户端、建立连接和迭代训练过程。

  这段代码演示了垂直联邦学习的基本流程，包括数据分区、模型参数共享和加密通信。每个客户端负责处理自己的数据部分并通过安全加密协议共享模型更新，以实现联合训练而不泄露原始数据。