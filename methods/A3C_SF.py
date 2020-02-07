
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
        self.v_target = tf.placeholder(tf.float32, [None], 'Vtarget')

        input = {"state":self.s}
        out = self.Model(input)
        self.a_prob = out["actor"]
        self.v = out["critic"]
        self.state_pred = out["prediction"]

        if globalAC is None:   # get global network
            with tf.variable_scope(scope):
                self.a_params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Actor')
                self.c_params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Critic')
                self.s_params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Reconstruction')
        else:   # local net, calculate losses
            self.buffer = [Trajectory(depth=6) for _ in range(nTrajs)]
            with tf.variable_scope(scope+"_update"):

                self.a_params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Actor')
                self.c_params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Critic')
                self.s_params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Reconstruction')

                td = tf.subtract(self.v_target, self.v, name='TD_error')
                with tf.name_scope('c_loss'):
                    self.c_loss = tf.reduce_mean(tf.square(td))

                with tf.name_scope('a_loss'):
                    log_prob = tf.reduce_sum(tf.log(self.a_prob + 1e-5) * tf.one_hot(self.a_his, actionSize, dtype=tf.float32), axis=1, keep_dims=True)
                    exp_v = log_prob * tf.stop_gradient(td)
                    entropy = -tf.reduce_sum(self.a_prob * tf.log(self.a_prob + 1e-5),
                                             axis=1, keep_dims=True)  # encourage exploration
                    self.exp_v = HPs["EntropyBeta"] * entropy + exp_v
                    self.a_loss = tf.reduce_mean(-self.exp_v)

                with tf.name_scope('s_loss'):
                    self.s_loss = tf.losses.mean_squared_error(self.state_pred,self.s_next)

                with tf.name_scope('local_grad'):
                    self.a_grads = tf.gradients(self.a_loss, self.a_params)
                    self.c_grads = tf.gradients(self.c_loss, self.c_params)
                    self.s_grads = tf.gradients(self.s_loss, self.s_params)

            with tf.name_scope('sync'):
                with tf.name_scope('pull'):
                    self.pull_a_params_op = [l_p.assign(g_p) for l_p, g_p in zip(self.a_params, globalAC.a_params)]
                    self.pull_c_params_op = [l_p.assign(g_p) for l_p, g_p in zip(self.c_params, globalAC.c_params)]
                    self.pull_s_params_op = [l_p.assign(g_p) for l_p, g_p in zip(self.s_params, globalAC.s_params)]
                with tf.name_scope('push'):
                    self.update_a_op = tf.train.AdamOptimizer(HPs["Actor LR"]).apply_gradients(zip(self.a_grads, globalAC.a_params))
                    self.update_c_op = tf.train.AdamOptimizer(HPs["Critic LR"]).apply_gradients(zip(self.c_grads, globalAC.c_params))
                    self.update_s_op = tf.train.AdamOptimizer(HPs["Actor LR"]).apply_gradients(zip(self.s_grads, globalAC.s_params))

            self.update_ops = [self.update_a_op,self.update_c_op,self.update_s_op]
            self.pull_ops = [self.pull_a_params_op,self.pull_c_params_op,self.pull_s_params_op]
            self.grads = [self.a_grads,self.c_grads,self.s_grads]
            self.losses = [self.a_loss,self.c_loss,self.s_loss]

            self.a_loss_MA = MovingAverage(400)
            self.c_loss_MA = MovingAverage(400)
            self.s_loss_MA = MovingAverage(400)
            self.a_grad_MA = MovingAverage(400)
            self.c_grad_MA = MovingAverage(400)
            self.s_grad_MA = MovingAverage(400)

    def GetAction(self, state):
        """
        Contains the code to run the network based on an input.
        """
        s = state[np.newaxis, :]
        probs,v = self.sess.run([self.a_prob,self.v], {self.s: s})   # get probabilities for all actions

        return np.random.choice(np.arange(probs.shape[1]), p=probs.ravel()) ,[v]  # return a int and extra data that needs to be fed to buffer.

    def Update(self,HPs,episode=0):
        """
        The main update function for A3C. The function pushes gradients to the global AC Network.
        The second function is to Pull
        """
        #Process the data from the buffer
        for traj in range(len(self.buffer)):
            clip = -1
            try:
                for j in range(2):
                    clip = self.buffer[traj][4].index(True, clip + 1)
            except:
                clip=len(self.buffer[traj][4])

            td_target = self.ProcessBuffer(HPs,traj,clip)

            #Create a feedDict from the buffer
            feedDict = {
                self.s: self.buffer[traj][0][:clip],
                self.s_next: self.buffer[traj][3][:clip],
                self.a_his: np.asarray(self.buffer[traj][1][:clip]).reshape(-1),
                self.v_target: td_target,
            }

            #Perform update operations
            _,_,_, a_loss, a_grads, c_loss, c_grads, s_loss=self.sess.run([self.update_a_op, self.update_c_op, self.update_s_op, self.a_loss, self.a_grads, self.c_loss, self.c_grads, self.s_loss], feedDict)   # local grads applied to global net.
            self.sess.run(self.pull_ops)   # global variables synched to the local net.

            self.a_loss_MA.append(a_loss)
            self.c_loss_MA.append(c_loss)
            self.s_loss_MA.append(s_loss)

            total_counter = 0
            vanish_counter = 0
            for grad in a_grads:
                total_counter += np.prod(grad.shape)
                vanish_counter += (np.absolute(grad)<1e-8).sum()
            self.a_grad_MA.append(vanish_counter/total_counter)

            total_counter = 0
            vanish_counter = 0
            for grad in c_grads:
                total_counter += np.prod(grad.shape)
                vanish_counter += (np.absolute(grad)<1e-8).sum()

            self.c_grad_MA.append(vanish_counter/total_counter)

    def GetStatistics(self):
        dict = {"Training Results/Vanishing Gradient Actor":self.a_grad_MA(),
        "Training Results/Critic Loss":self.a_loss_MA(),
        "Training Results/Actor Loss":self.c_loss_MA(),
        "Training Results/State Pred Loss":self.s_loss_MA(),
        "Training Results/Vanishing Gradient Critic":self.c_grad_MA(),}
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

        td_target, _ = gae(self.buffer[traj][2][:clip],self.buffer[traj][5][:clip],0,HPs["Gamma"],HPs["lambda"])
        # tracker.print_diff()
        return td_target

        # buffer_v_s_ = []
        # for r in self.buffer[2][::-1]:
        #     if self.buffer[4][-1]:
        #         v_s_ = 0   # terminal
        #     else:
        #         v_s_ = self.sess.run(self.v, {self.s: self.buffer[3][-1][np.newaxis, :]})[0, 0]
        #
        #     v_s_ = r + HPs["Gamma"] * v_s_
        #     buffer_v_s_.append(v_s_)
        #
        # buffer_v_s_.reverse()
        # self.buffer[2] = buffer_v_s_

    @property
    def getVars(self):
        return self.Model.getVars(self.scope)

    @property
    def getAParams(self):
        return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ 'Actor')

    @property
    def getCParams(self):
        return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Critic')
