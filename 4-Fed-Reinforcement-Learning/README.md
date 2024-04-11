# 联邦强化学习

![架构](https://github.com/liamhebert/FedFormer/raw/main/FedFormer%20Architecture.png)

 联邦强化学习中的一个核心问题是如何将多个智能体的见解聚合到一个模型中。 FedFormer，利用 Transformer 注意力机制来从不同学习智能体的模型中上下文地聚合嵌入。通过这种方式，根据当前智能体的环境和学习关系来关注其他智能体的贡献，从而提供更有效和高效的联邦学习。

![MT10 上的结果](https://github.com/liamhebert/FedFormer/raw/main/figure2-all-tasks-results.png)

在这些图表中，Soft Actor Critique (SAC) 的结果是在所有环境上训练的（代表不保留隐私），而 FedFormer 和 FedAvg 是使用具有不同子环境集合的 5 个智能体分别训练的（代表多个智能体保留隐私）![FedFormer 扩展的结果](https://github.com/liamhebert/FedFormer/raw/main/figure3-scaling-fedavg-results.png)

当智能体数量超过 5 个时，我们发现 FedFormer 比 FedAvg 更加稳健，尽管智能体数量增加，但性能始终优于 FedAvg。

## 安装：

我们在 'environment.yml' 中提供了 conda 环境文件，其中包含了所有的 Python 依赖项。您可以通过以下方式创建环境：

```
shellCopy code
conda env create --prefix <env-location> -f environment.yml
```

还需要安装 [MuJoCo 2.10](https://github.com/openai/mujoco-py)。作为我们源代码的一部分，我们从 [RLKit](https://github.com/rail-berkeley/rlkit) 和 [Garage](https://github.com/rlworkgroup/garage) 借用了一些模块。

## 运行：

运行我们代码的主要入口点是 'main.py'。在该文件中，您可以找到一个包含可调整超参数的字典，例如：

```
pythonCopy codevariant = dict(
        algorithm="FedFormer",
        task=task,
        overlap=False, # 环境是否应重叠
        fedFormer=True, # 是否使用 FedFormer Q-Functions
        run_name="FedFormer - " + str(agents) + " - " + str(seed), # 用于记录目的
        from_saved=0, # 保存编码器网络的数量
        layer_size=400, # 隐藏层大小
        replay_buffer_size=int(1E6), 
        num_jobs_per_gpu=2, # 每个 GPU 并行训练的智能体数量
        transformer_num_layers=2, # 要使用的 Transformer 编码器层数
        num_agents=agents, # 初始化的联邦智能体数量
        transformer_layer_kwargs=dict(
            d_model=400, # 每个 Transformer 层的隐藏大小
            nhead=4 # 初始化的注意力头数
        ),
        algorithm_kwargs=dict(
            num_epochs=500, # 250
            num_eval_steps_per_epoch=500, # 5000
            num_trains_per_train_loop=500, # 600
            num_expl_steps_per_train_loop=400, # 400
            min_num_steps_before_training=400, # 400
            max_path_length=500, # 500
            batch_size=500, # 1200
            
        ),
        trainer_kwargs=dict(
            discount=0.99,
            soft_target_tau=5e-3,
            target_update_period=1,
            policy_lr=3E-4,
            qf_lr=3E-4,
            reward_scale=1,
            use_automatic_entropy_tuning=True,
        ),
    )
```

修改后，可以运行：

```
cssCopy code
python main.py --task=<task> --seed=<seed> --agents=<num_agents> 
```

其中 "task" 是 [10 个 MetaWorld 任务](https://meta-world.github.io/figures/ml10.gif) 中的一个，例如 `reach-v2` 和 `window-close-v2`，"seed" 是一个用于设置环境分布的随机种子，"agents" 是要联合的智能体数量。

实验运行完成后，可以通过运行以下命令查看所有结果：

```
cssCopy code
tensorboard --logdir=runs
```

