# 纵向联邦后门攻击方法

在文件中，模型结构和数据处理适用于 CIFAR10 数据集。您可以自行下载 CIFAR10 数据并直接在其上运行我们的代码。

您可以按照以下步骤测试攻击方案：

1. 生成一个干净模型以验证基线分类准确率：

   ```bash
   python clean_train.py --clean-epoch 80 --dup 0 --multies 4 --unit 0.25
   ```

   您可以运行 `python clean_train.py -h` 查看每个参数的含义。

   在这一步之后，您将得到一个完成 100 轮训练的干净模型，以及一个经过预污染训练的模型，该模型完成了 80 轮干净训练，用于后续的后门攻击。

2. 污染模型并生成特殊触发向量：

   ```bash
   python poison_train.py --label 0 --dup 0 --magnification 6 --multies 4 --unit 0.25 --clean-epoch 80
   ```

   在这一步中，该过程将对第一步中预污染训练的模型进行污染和训练，以完成剩余的 20 轮训练。请注意，dup、multies、unit 和 clean-epoch 的参数值需要与第一步中的参数保持一致。

   在这一步之后，您将获得一个完成 100 轮训练的后门模型，以及其触发向量。

3. 在触发向量上添加适当的噪声，以避免在底层模型上传过程中重复出现：

   ```bash
   python add_noise.py --multies 4 --unit 0.25
   ```

   您可以查看带有噪声的触发向量的攻击成功率。

请注意，您可以打开 `noise_vec_0.csv` 和 `normal_vec_0.csv` 直接观察它们之间的微小差异，并根据我们的论文调整噪声的大小至适当的范围。
