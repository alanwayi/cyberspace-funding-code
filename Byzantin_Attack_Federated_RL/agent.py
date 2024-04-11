import os
import numpy as np
import torch
import torch.optim as optim
from torch.multiprocessing import Pool
from tqdm import tqdm
from sklearn import metrics
from matplotlib import pyplot as plt
from itertools import repeat
from scipy.interpolate import Rbf
import scipy.stats as st

from worker import Worker
from utils import torch_load_cpu, get_inner_model, env_wrapper

class Memory:
    def __init__(self):
        self.steps = {}
        self.eval_values = {}
        self.training_values = {}

def euclidean_dist(x, y):
    """
    Args:
      x: pytorch Variable, with shape [m, d]
      y: pytorch Variable, with shape [n, d]
    Returns:
      dist: pytorch Variable, with shape [m, n]
    """
    m, n = x.size(0), y.size(0)
    xx = torch.pow(x, 2).sum(1, keepdim=True).expand(m, n)
    yy = torch.pow(y, 2).sum(1, keepdim=True).expand(n, m).T
    dist = xx + yy
    dist.addmm_(1, -2, x, y.T)
    dist[dist < 0] = 0
    dist = dist.sqrt()
    return dist

def worker_run(worker, param, opts, Batch_size, seed):
    
    # distribute current parameters
    worker.load_param_from_master(param)
    worker.env.seed(seed)
    
    # get returned gradients and info from all agents        
    out = worker.train_one_epoch(Batch_size, opts.device, opts.do_sample_for_training)
    
    # store all values
    return out
    


class Agent:
    
    def __init__(self, opts):
        
        # figure out the options
        self.opts = opts
        
        # setup arrays for distrubuted RL
        self.world_size = opts.num_worker
        
        # figure out the master
        self.master = Worker(
                id = 0,
                is_Byzantine = False,
                env_name = opts.env_name,
                gamma = opts.gamma,
                hidden_units = opts.hidden_units, 
                activation = opts.activation, 
                output_activation = opts.output_activation,
                max_epi_len = opts.max_epi_len,
                opts = opts
        ).to(opts.device)
        
        # figure out a copy of the master node for importance sampling purpose
        self.old_master = Worker(
                id = -1,
                is_Byzantine = False,
                env_name = opts.env_name,
                gamma = opts.gamma,
                hidden_units = opts.hidden_units, 
                activation = opts.activation, 
                output_activation = opts.output_activation,
                max_epi_len = opts.max_epi_len,
                opts = opts
        ).to(opts.device)
        
        # figure out all the actors
        self.workers = []
        self.true_Byzantine = []
        for i in range(self.world_size):
            self.true_Byzantine.append(True if i < opts.num_Byzantine else False)
            self.workers.append( Worker(
                                    id = i+1,
                                    is_Byzantine = True if i < opts.num_Byzantine else False,
                                    env_name = opts.env_name,
                                    gamma = opts.gamma,
                                    hidden_units = opts.hidden_units, 
                                    activation = opts.activation, 
                                    output_activation = opts.output_activation,
                                    attack_type =  opts.attack_type,
                                    max_epi_len = opts.max_epi_len,
                                    opts = opts
                            ).to(opts.device))
        print(f'{opts.num_worker} workers initilized with {opts.num_Byzantine if opts.num_Byzantine >0 else "None"} of them are Byzantine.')
        
        if not opts.eval_only:
            # figure out the optimizer
            self.optimizer = optim.Adam(self.master.logits_net.parameters(), lr = opts.lr_model)
        
        self.pool = Pool(self.world_size)
        self.memory = Memory()
    
    def load(self, load_path):
        assert load_path is not None
        load_data = torch_load_cpu(load_path)
        # load data for actor
        model_actor = get_inner_model(self.master.logits_net)
        model_actor.load_state_dict({**model_actor.state_dict(), **load_data.get('master', {})})
        
        if not self.opts.eval_only:
            # load data for optimizer
            self.optimizer.load_state_dict(load_data['optimizer'])
            for state in self.optimizer.state.values():
                for k, v in state.items():
                    if torch.is_tensor(v):
                        state[k] = v.to(self.opts.device)
            # load data for torch and cuda
            torch.set_rng_state(load_data['rng_state'])
            if self.opts.use_cuda:
                torch.cuda.set_rng_state_all(load_data['cuda_rng_state'])
    
        print(' [*] Loading data from {}'.format(load_path))
        
    
    def save(self, epoch, run_id):
        print('Saving model and state...')
        torch.save(
            {
                'master': get_inner_model(self.master.logits_net).state_dict(),
                'optimizer': self.optimizer.state_dict(),
                'rng_state': torch.get_rng_state(),
                'cuda_rng_state': torch.cuda.get_rng_state_all(),
            },
            os.path.join(self.opts.save_dir, 'r{}-epoch-{}.pt'.format(run_id,epoch))
        )
    
    
    def eval(self):
        # turn model to eval mode
        self.master.eval()
        
    def train(self):
        # turn model to trainig mode
        self.master.train()
        
    
    def start_training(self, tb_logger = None, run_id = None):
        
        # parameters of running
        opts = self.opts

        # for storing number of trajectories sampled
        step = 0
        epoch = 0
        ratios_step = 0
        
        # Start the training loop
        while step <= opts.max_trajectories:
            # epoch for storing checkpoints of model
            epoch += 1
            
            # Turn model into training mode
            print('\n\n')
            print("|",format(f" Training step {step} run_id {run_id} in {opts.seeds}","*^60"),"|")
            self.train()
            
            # setup lr_scheduler
            print("Training with lr={:.3e} for run {}".format(self.optimizer.param_groups[0]['lr'], opts.run_name) , flush=True)
            
            # some emplty list for training and logging purpose
            gradient = []
            batch_loss = []
            batch_rets = []
            batch_lens = []
            
            # distribute current params and Batch_Size to all workers
            param = get_inner_model(self.master.logits_net).state_dict()
            
            if opts.FedPG_BR:
                Batch_size = np.random.randint(opts.Bmin, opts.Bmax + 1)
            else:
                Batch_size = opts.B
        
            seeds = np.random.randint(1,100000, self.world_size).tolist()
            args = zip(self.workers,
                       repeat(param),
                       repeat(opts),
                       repeat(Batch_size),
                       seeds)
            
            results = self.pool.starmap(worker_run, args)

            #  collect the gradient(for training), loss(for logging only), returns(for logging only), and epi_length(for logging only) from workers         
            for out in tqdm(results, desc='Worker node'):
                grad, loss, rets, lens = out
            
                # store all values
                gradient.append(grad)

                batch_loss.append(loss)
                batch_rets.append(rets)
                batch_lens.append(lens)
            
            
            # simulate FedScsPG-attack (if needed) on server for demo
            if opts.attack_type == 'FedScsPG-attack' and opts.num_Byzantine > 0:  
                for idx,_ in enumerate(self.master.parameters()):
                    tmp = []
                    for bad_worker in range(opts.num_Byzantine):
                        tmp.append(gradient[bad_worker][idx].view(-1))
                    tmp = torch.stack(tmp)

                    estimated_2sigma = euclidean_dist(tmp, tmp).max()
                    estimated_mean = tmp.mean(0)
                    
                    # change the gradient to be estimated_mean + 3sigma (with a random direction rnd)
                    rnd = torch.rand(gradient[0][idx].shape) * 2. - 1.
                    rnd = rnd / rnd.norm()
                    attacked_gradient = estimated_mean.view(gradient[bad_worker][idx].shape) + rnd * estimated_2sigma * 3. / 2.
                    for bad_worker in range(opts.num_Byzantine):
                        gradient[bad_worker][idx] = attacked_gradient
                        
              
            # make the old policy as a copy of the current master node
            self.old_master.load_param_from_master(param)
            
            # do Aggregate Algorithm to detect Byzantine worker on master node
            if opts.FedPG_BR:
                
                # flatten the gradient vectors of each worker and put them together, shape [num_worker, -1]
                mu_vec = None
                for idx,item in enumerate(self.old_master.parameters()):
                    # stack gradient[idx] from all worker nodes
                    grad_item = []
                    for i in range(self.world_size):
                         grad_item.append(gradient[i][idx])
                    grad_item = torch.stack(grad_item).view(self.world_size,-1)
                
                    # concat stacked grad vector
                    if mu_vec is None:
                        mu_vec = grad_item.clone()
                    else:
                        mu_vec = torch.cat((mu_vec, grad_item.clone()), -1)
                    
                # calculate the norm distance between each worker's gradient vector, shape [num_worker, num_worker]
                dist = euclidean_dist(mu_vec, mu_vec)
                
                # calculate C, Variance Bound V, thresold, and alpha
                V = 2 * np.log(2 * opts.num_worker / opts.delta)
                sigma = opts.sigma

                threshold = 2 * sigma * np.sqrt(V / Batch_size)
                alpha = opts.alpha
                
                # to find MOM: |dist <= threshold| > 0.5 * num_worker
                mu_med_vec = None
                k_prime = (dist <= threshold).sum(-1) > (0.5 * self.world_size)
                
                # computes the mom of the gradients, mu_med_vec, and
                # filter the gradients it believes to be Byzantine and store the index of non-Byzantine graidents in Good_set
                if torch.sum(k_prime) > 0:
                    mu_mean_vec = torch.mean(mu_vec[k_prime],0).view(1,-1)
                    mu_med_vec = mu_vec[k_prime][euclidean_dist(mu_mean_vec, mu_vec[k_prime]).argmin()].view(1,-1)
                    # applying R1 to filter
                    Good_set = euclidean_dist(mu_vec, mu_med_vec) <= 1 * threshold
                else:
                    Good_set = k_prime # skip this step if k_prime is emplty (i.e., all False)
                
                # avoid the scenarios that Good_set is empty or can have |Gt| < (1 − α)K.
                if torch.sum(Good_set) < (1 - alpha) * self.world_size or torch.sum(Good_set) == 0:
                    
                    # re-calculate mom of the gradients
                    k_prime = (dist <= 2 * sigma).sum(-1) > (0.5 * self.world_size)
                    if torch.sum(k_prime) > 0:
                        mu_mean_vec = torch.mean(mu_vec[k_prime],0).view(1,-1)
                        mu_med_vec = mu_vec[k_prime][euclidean_dist(mu_mean_vec, mu_vec[k_prime]).argmin()].view(1,-1)
                        # re-filter with R2
                        Good_set = euclidean_dist(mu_vec, mu_med_vec) <= 2 * sigma
                    else:
                        Good_set = torch.zeros(self.world_size,1).to(opts.device).bool()
            
            # else will treat all nodes as non-Byzantine nodes
            else:
                Good_set = torch.ones(self.world_size,1).to(opts.device).bool()
            
            # calculate number of good gradients for logging
            N_good = torch.sum(Good_set)
            
            # aggregate all detected non-Byzantine gradients to get mu
            if N_good > 0:
                mu = []
                for idx,item in enumerate(self.old_master.parameters()):
                    grad_item = []
                    for i in range(self.world_size):
                        if Good_set[i]: # only aggregate non-Byzantine gradients
                            grad_item.append(gradient[i][idx])
                    mu.append(torch.stack(grad_item).mean(0))
            else: # if still all nodes are detected to be Byzantine, check the sigma. If siagma is set properly, this situation will not happen.
                mu = None
            
            # perform gradient update in master node
            grad_array = [] # store gradients for logging

            if opts.FedPG_BR or opts.SVRPG:
                
                if opts.FedPG_BR:
                    # for n=1 to Nt ~ Geom(B/B+b) do grad update
                    b = opts.b
                    N_t = np.random.geometric(p= 1 - Batch_size/(Batch_size + b))
                    
                elif opts.SVRPG:
                    b = opts.b
                    N_t = opts.N
                    
                for n in tqdm(range(N_t), desc = 'Master node'):
                   
                    # calculate new gradient in master node
                    self.optimizer.zero_grad()

                    # sample b trajectory using the latest policy (\theta_n) of master node
                    weights, new_logp, batch_rets, batch_lens, batch_states, batch_actions = self.master.collect_experience_for_training(b, 
                                                                                                                                 opts.device, 
                                                                                                                                 record = True,
                                                                                                                                 sample = opts.do_sample_for_training)
                        
                         
                    # calculate gradient for the new policy (\theta_n)
                    loss_new = -(new_logp * weights).mean()
                    self.master.logits_net.zero_grad()
                    loss_new.backward()
                    
                    if mu:
                        # get the old log_p with the old policy (\theta_0) but fixing the actions to be the same as the sampled trajectory
                        old_logp = []
                        for idx, obs in enumerate(batch_states):
                            # act in the environment with the fixed action
                            obs = env_wrapper(opts.env_name, obs)
                            _, old_log_prob = self.old_master.logits_net(torch.as_tensor(obs, dtype=torch.float32).to(opts.device), 
                                                                         fixed_action = batch_actions[idx])
                            # store in the old_logp
                            old_logp.append(old_log_prob)
                        old_logp = torch.stack(old_logp)
                        
                        # Finding the ratio (pi_theta / pi_theta__old):
                        # print(old_logp, new_logp)
                        ratios = torch.exp(old_logp.detach() - new_logp.detach())
                        ratios_step += 1
                        
                        # calculate gradient for the old policy (\theta_0)
                        loss_old = -(old_logp * weights * ratios).mean()
                        self.old_master.logits_net.zero_grad()
                        loss_old.backward()
                        grad_old = [item.grad for item in self.old_master.parameters()]   
                    
                        # early stop if ratio is not within [0.995, 1.005]
                        if torch.abs(ratios.mean()) < 0.995 or torch.abs(ratios.mean()) > 1.005:
                            N_t = n
                            break
                        
                        if tb_logger is not None:
                            tb_logger.add_scalar(f'params/ratios_{run_id}', ratios.mean(), ratios_step)
                        
                        # adjust and set the gradient for latest policy (\theta_n)
                        for idx,item in enumerate(self.master.parameters()):
                            item.grad = item.grad - grad_old[idx] + mu[idx]  # if mu is None, use grad from master 
                            grad_array += (item.grad.data.view(-1).cpu().tolist())
                        
                    # take a gradient step
                    self.optimizer.step()
        
            else: # GOMDP in this case
                
                b = 0
                N_t = 0
                
                # perform gradient descent with mu vector
                for idx,item in enumerate(self.master.parameters()):
                    item.grad = mu[idx]
                    grad_array += (item.grad.data.view(-1).cpu().tolist())
                    
                # take a gradient step
                self.optimizer.step()  
            
            print('\nepoch: %3d \t loss: %.3f \t return: %.3f \t ep_len: %.3f \t N_good: %d'%
                (epoch, np.mean(batch_loss), np.mean(batch_rets), np.mean(batch_lens), N_good))
            
            # current step: number of trajectories sampled
            # step += max(Batch_size, b * N_t) if self.world_size > 1 else Batch_size + b * N_t
            step += round((Batch_size * self.world_size  + b * N_t) / (1 + self.world_size)) if self.world_size > 1 else Batch_size + b * N_t
            
            # Logging to tensorboard
            if(tb_logger is not None):
                
                # training log
                tb_logger.add_scalar(f'train/total_rewards_{run_id}', np.mean(batch_rets), step)
                tb_logger.add_scalar(f'train/epi_length_{run_id}', np.mean(batch_lens), step)
                tb_logger.add_scalar(f'train/loss_{run_id}', np.mean(batch_loss), step)
                # grad log
                tb_logger.add_scalar(f'grad/grad_{run_id}', np.mean(grad_array), step)
                # optimizer log
                tb_logger.add_scalar(f'params/lr_{run_id}', self.optimizer.param_groups[0]['lr'], step)
                tb_logger.add_scalar(f'params/N_t_{run_id}', N_t, step)

                # Byzantine filtering log
                if opts.FedPG_BR:
                    
                    y_true = self.true_Byzantine
                    y_pred = (~ Good_set).view(-1).cpu().tolist()
                    
                    dist_Byzantine = dist[:opts.num_Byzantine][:,:opts.num_Byzantine]
                    dist_good = dist[opts.num_Byzantine:][:,opts.num_Byzantine:]
                    dist_good_Byzantine = dist[:opts.num_Byzantine][:,opts.num_Byzantine:]
    
                    if opts.num_Byzantine > 0:
                        tb_logger.add_scalar(f'grad_norm_mean/Byzantine_{run_id}', torch.mean(dist_Byzantine), step)
                        tb_logger.add_scalar(f'grad_norm_max/Byzantine_{run_id}', torch.max(dist_Byzantine), step)
                        tb_logger.add_scalar(f'grad_norm_mean/Good_{run_id}', torch.mean(dist_good), step)
                        tb_logger.add_scalar(f'grad_norm_max/Good_{run_id}', torch.max(dist_good), step)
                        tb_logger.add_scalar(f'grad_norm_mean/Between_{run_id}', torch.mean(dist_good_Byzantine), step)
                        tb_logger.add_scalar(f'grad_norm_max/Between_{run_id}', torch.max(dist_good_Byzantine), step)
                  
                        tb_logger.add_scalar(f'Byzantine/precision_{run_id}', metrics.precision_score(y_true, y_pred), step)
                        tb_logger.add_scalar(f'Byzantine/recall_{run_id}', metrics.recall_score(y_true, y_pred), step)
                        tb_logger.add_scalar(f'Byzantine/f1_score_{run_id}', metrics.f1_score(y_true, y_pred), step)
                
                    tb_logger.add_scalar(f'Byzantine/threshold_{run_id}', threshold, step)
                    tb_logger.add_scalar(f'grad_norm_mean/ALL_{run_id}', torch.mean(dist), step)
                    tb_logger.add_scalar(f'grad_norm_max/ALL_{run_id}', torch.max(dist), step)
                    tb_logger.add_scalar(f'Byzantine/N_good_pred_{run_id}', N_good, step)
                        
                # for performance plot
                if run_id not in self.memory.steps.keys():
                    self.memory.steps[run_id] = []
                    self.memory.eval_values[run_id] = []
                    self.memory.training_values[run_id] = []
                
                self.memory.steps[run_id].append(step)
                self.memory.training_values[run_id].append(np.mean(batch_rets))
                             
                
            # do validating
            eval_reward = self.start_validating(tb_logger, step, max_steps = opts.val_max_steps, render = opts.render, run_id = run_id)
            if(tb_logger is not None):
                 self.memory.eval_values[run_id].append(eval_reward)
                            
            # save current model
            if not opts.no_saving:
                self.save(epoch, run_id)
                
    
    # validate the new model   
    def start_validating(self,tb_logger = None, id = 0, max_steps = 1000, render = False, run_id = 0, mode = 'human'):
        print('\nValidating...', flush=True)
        
        val_ret = 0.0
        val_len = 0.0
        
        for _ in range(self.opts.val_size):
            epi_ret, epi_len, _ = self.master.rollout(self.opts.device, max_steps = max_steps, render = render, sample = False, mode = mode, save_dir = './outputs/', filename = f'gym_{run_id}_{_}.gif')
            val_ret += epi_ret
            val_len += epi_len
        
        val_ret /= self.opts.val_size
        val_len /= self.opts.val_size
        
        print('\nGradient step: %3d \t return: %.3f \t ep_len: %.3f'%
                (id,  np.mean(val_ret), np.mean(val_len)))
        
        if(tb_logger is not None):
            tb_logger.add_scalar(f'validate/total_rewards_{run_id}', np.mean(val_ret), id)
            tb_logger.add_scalar(f'validate/epi_length_{run_id}', np.mean(val_len), id)
            tb_logger.close()
        
        return np.mean(val_ret)
    
    # logging performance summary
    
    
    def plot_graph(self, array):
        plt.ioff()
        fig = plt.figure(figsize=(8,4))
        y = []
        
        for id in self.memory.steps.keys():
             x = self.memory.steps[id]
             y.append(Rbf(x, array[id], function = 'linear')(np.arange(self.opts.max_trajectories)))
        
        mean = np.mean(y, axis=0)
        
        l, h = st.norm.interval(0.90, loc=np.mean(y, axis = 0), scale=st.sem(y, axis = 0))
        
        plt.plot(mean)
        plt.fill_between(range(int(self.opts.max_trajectories)), l, h, alpha = 0.5)
        
        axes = plt.axes()
        axes.set_ylim([self.opts.min_reward, self.opts.max_reward])
        
        plt.xlabel("Number of Trajectories")
        plt.ylabel("Reward")
        plt.grid(True)
        plt.tight_layout()
        return fig
    
    
    def log_performance(self, tb_logger):
       
        eval_img = self.plot_graph(self.memory.eval_values)
        training_img = self.plot_graph(self.memory.training_values)
        tb_logger.add_figure(f'validate/performance_until_{len(self.memory.steps.keys())}_runs', eval_img, len(self.memory.steps.keys()))
        tb_logger.add_figure(f'train/performance_until_{len(self.memory.steps.keys())}_runs', training_img, len(self.memory.steps.keys()))        
