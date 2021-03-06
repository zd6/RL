
"""
To Do:
-Add an optional input for the networks so they can be defined in a main run script.
-Test
-Combine Training Operation
"""
from .method import Method
from .buffer import Trajectory
from .AdvantageEstimator import gae
import tensorflow as tf
import numpy as np
from utils.utils import MovingAverage
from utils.record import Record

class A3C(Method):

    def __init__(self,sharedModel,sess,stateShape,actionSize,scope,HPs,globalAC=None,nTrajs=1):
        """
        Initializes I/O placeholders used for Tensorflow session runs.
        Initializes and Actor and Critic Network to be used for the purpose of RL.
        """
        #Placeholders

        self.sess=sess
        self.scope=scope
        self.Model = sharedModel
        self.s = tf.placeholder(tf.float32, [None] + stateShape, 'S')
        self.s_next = tf.placeholder(tf.float32, [None] + stateShape, 'S_next')
        self.a_his = tf.placeholder(tf.int32, [None, ], 'A')
        self.reward = tf.placeholder(tf.float32, [None, ], 'R')
        self.v_target = tf.placeholder(tf.float32, [None], 'Vtarget')
        self.advantage = tf.placeholder(tf.float32, [None], 'Advantage')
        self.td_target = tf.placeholder(tf.float32, [None, 64], 'TDtarget')

        input = {"state":self.s}
        out = self.Model(input)
        self.a_prob = out["actor"]
        self.v = out["critic"]
        self.state_pred = out["prediction"]
        self.reward_pred = out["reward_pred"]
        self.phi = out["phi"]
        self.psi = out["psi"]

        if globalAC is None:   # get global network
            with tf.variable_scope(scope):
                self.a_params = self.Model.GetVariables("Actor")
                self.c_params = self.Model.GetVariables("Critic")
                self.s_params = self.Model.GetVariables("Reconstruction")
                self.r_params = self.Model.GetVariables("Reward")
        else:   # local net, calculate losses
            self.buffer = [Trajectory(depth=8) for _ in range(nTrajs)]
            with tf.variable_scope(scope+"_update"):

                self.a_params = self.Model.GetVariables("Actor")
                self.c_params = self.Model.GetVariables("Critic")
                self.s_params = self.Model.GetVariables("Reconstruction")
                self.r_params = self.Model.GetVariables("Reward")

                with tf.name_scope('c_loss'):
                    sf_error = tf.subtract(self.td_target, self.psi, name='TD_error')
                    sf_error = tf.square(sf_error)
                    self.c_loss = tf.reduce_mean(sf_error,name="sf_loss")

                with tf.name_scope('a_loss'):
                    # td = tf.subtract(self.v_target, self.v, name='TD_error')
                    log_prob = tf.reduce_sum(tf.log(self.a_prob + 1e-5) * tf.one_hot(self.a_his, actionSize, dtype=tf.float32), axis=1, keep_dims=True)
                    exp_v = log_prob * self.advantage
                    entropy = -tf.reduce_sum(self.a_prob * tf.log(self.a_prob + 1e-5),axis=1, keep_dims=True)  # encourage exploration
                    self.exp_v = HPs["EntropyBeta"] * entropy + exp_v
                    self.a_loss = tf.reduce_mean(-self.exp_v)

                with tf.name_scope('s_loss'):
                    self.s_loss = tf.losses.mean_squared_error(self.state_pred,self.s_next)

                with tf.name_scope('r_loss'):
                    self.r_loss = tf.losses.mean_squared_error(self.reward,tf.squeeze(self.reward_pred))

                with tf.name_scope('local_grad'):
                    self.a_grads = tf.gradients(self.a_loss, self.a_params)
                    self.c_grads = tf.gradients(self.c_loss, self.c_params)
                    self.s_grads = tf.gradients(self.s_loss, self.s_params)
                    self.r_grads = tf.gradients(self.r_loss, self.r_params)

            with tf.name_scope('sync'):
                with tf.name_scope('pull'):
                    self.pull_a_params_op = [l_p.assign(g_p) for l_p, g_p in zip(self.a_params, globalAC.a_params)]
                    self.pull_c_params_op = [l_p.assign(g_p) for l_p, g_p in zip(self.c_params, globalAC.c_params)]
                    self.pull_s_params_op = [l_p.assign(g_p) for l_p, g_p in zip(self.s_params, globalAC.s_params)]
                    self.pull_r_params_op = [l_p.assign(g_p) for l_p, g_p in zip(self.r_params, globalAC.r_params)]

                with tf.name_scope('push'):
                    self.update_a_op = tf.train.AdamOptimizer(HPs["Actor LR"]).apply_gradients(zip(self.a_grads, globalAC.a_params))
                    self.update_c_op = tf.train.AdamOptimizer(HPs["Critic LR"]).apply_gradients(zip(self.c_grads, globalAC.c_params))
                    self.update_s_op = tf.train.AdamOptimizer(HPs["State LR"]).apply_gradients(zip(self.s_grads, globalAC.s_params))
                    self.update_r_op = tf.train.AdamOptimizer(HPs["Reward LR"]).apply_gradients(zip(self.r_grads, globalAC.r_params))

            self.update_ops = [self.update_a_op,self.update_c_op,self.update_s_op,self.update_r_op]
            self.pull_ops = [self.pull_a_params_op,self.pull_c_params_op,self.pull_s_params_op,self.pull_r_params_op]
            self.grads = [self.a_grads,self.c_grads,self.s_grads,self.r_grads]
            self.losses = [self.a_loss,self.c_loss,self.s_loss,self.r_loss]

            self.grad_MA = [MovingAverage(400) for i in range(len(self.grads))]
            self.loss_MA = [MovingAverage(400) for i in range(len(self.grads))]
            self.labels = ["Actor","Critic","State","Reward"]

            self.HPs = HPs

    def GetAction(self, state,episode=0,step=0,deterministic=False,debug=False):
        """
        Contains the code to run the network based on an input.
        """
        s = state[np.newaxis, :]
        probs,v,phi,psi = self.sess.run([self.a_prob,self.v, self.phi, self.psi], {self.s: s})   # get probabilities for all actions
        if deterministic:
            actions = np.array([np.argmax(prob / sum(prob)) for prob in probs])
        else:
            actions = np.array([np.random.choice(probs.shape[1], p=prob / sum(prob)) for prob in probs])
        if debug: print(probs)
        return actions ,[v,phi,psi]  # return a int and extra data that needs to be fed to buffer.

    def Update(self,HPs,episode=0,statistics=True):
        """
        The main update function for A3C. The function pushes gradients to the global AC Network.
        The second function is to Pull
        """
        samples=0
        for i in range(len(self.buffer)):
            samples +=len(self.buffer[i])
        if samples < self.HPs["BatchSize"]:
            return

        for traj in range(len(self.buffer)):
            clip = -1
            # try:
            #     for j in range(2):
            #         clip = self.buffer[traj][4].index(True, clip + 1)
            # except:
            #     clip=len(self.buffer[traj][4])

            v_target,advantages,td_target = self.ProcessBuffer(HPs,traj,clip)

            batches = len(self.buffer[traj][0][:clip])//self.HPs["MinibatchSize"]+1
            if "StackedDim" in self.HPs:
                if self.HPs["StackedDim"] > 1:
                    s_next = np.array_split(np.squeeze(self.buffer[traj][3][:clip])[:,:,:,-self.HPs["StackedDim"]:],3,batches)
                else:
                    s_next = np.array_split(np.expand_dims(np.stack(self.buffer[traj][3][:clip])[:,:,:,-self.HPs["StackedDim"]],3),batches)
            else:
                s_next = np.array_split(self.buffer[traj][3][:clip],batches)
            s = np.array_split(self.buffer[traj][0][:clip], batches)
            reward = np.array_split(np.asarray(self.buffer[traj][2][:clip]).reshape(-1),batches)
            psi_target = np.array_split(np.squeeze(td_target),batches)
            advantage = np.array_split(np.squeeze(np.asarray(advantages).reshape(-1)),batches)
            a_his = np.array_split(np.asarray(self.buffer[traj][1][:clip]).reshape(-1),batches)

            #Create a feedDict from the buffer
            for epoch in range(self.HPs["Epochs"]):
                #Create a feedDict from the buffer
                for i in range(batches):
                    feedDict = {
                        self.s: s[i],
                        self.reward: reward[i],
                        self.s_next: s_next[i],
                        self.a_his: a_his[i],
                        self.advantage: advantage[i],
                        self.td_target: psi_target[i],
                    }

                    if not statistics:
                        self.sess.run(self.update_ops, feedDict)   # local grads applied to global net.
                    else:
                        #Perform update operations
                        try:
                            out = self.sess.run(self.update_ops+self.losses+self.grads, feedDict)   # local grads applied to global net.
                            out = np.array_split(out,3)
                            losses = out[1]
                            grads = out[2]

                            for i,loss in enumerate(losses):
                                self.loss_MA[i].append(loss)

                            for i,grads_i in enumerate(grads):
                                total_counter = 0
                                vanish_counter = 0
                                for grad in grads_i:
                                    total_counter += np.prod(grad.shape)
                                    vanish_counter += (np.absolute(grad)<1e-8).sum()
                                self.grad_MA[i].append(vanish_counter/total_counter)
                        except:
                            out = self.sess.run(self.update_ops+self.losses, feedDict)   # local grads applied to global net.
                            out = np.array_split(out,2)
                            losses = out[1]

                            for i,loss in enumerate(losses):
                                self.loss_MA[i].append(loss)

        self.sess.run(self.pull_ops)   # global variables synched to the local net.

        self.ClearTrajectory()


    def GetStatistics(self):
        dict ={}
        for i,label in enumerate(self.labels):
            dict["Training Results/Vanishing Gradient " + label] = self.grad_MA[i]()
            dict["Training Results/Loss " + label] = self.loss_MA[i]()
        return dict


    def ProcessBuffer(self,HPs,traj,clip):
        """
        Process the buffer to calculate td_target.

        Parameters
        ----------
        Model : HPs
            Hyperparameters for training.
        traj : Trajectory
            Data stored by the neural network.
        clip : list[bool]
            List where the trajectory has finished.

        Returns
        -------
        td_target : list
            List Temporal Difference Target for particular states.
        advantage : list
            List of advantages for particular actions.
        """
        # print("Starting Processing Buffer\n")
        # tracker.print_diff()

        v_target, advantage = gae(self.buffer[traj][2][:clip],self.buffer[traj][5][:clip],0,HPs["Gamma"],HPs["lambda"])

        td_target, _ = gae(self.buffer[traj][6][:clip], self.buffer[traj][7][:clip], np.zeros_like(self.buffer[traj][6][0]),HPs["Gamma"],HPs["lambda"])
        # tracker.print_diff()
        return v_target,advantage, td_target


    @property
    def getVars(self):
        return self.Model.getVars(self.scope)

    @property
    def getAParams(self):
        return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ 'Actor')

    @property
    def getCParams(self):
        return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Critic')
