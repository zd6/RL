
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

class OffPolicySF(Method):

    def __init__(self,sharedModel,sess,stateShape,actionSize,scope,HPs,nTrajs=1):
        """
        Off policy Successor Representation using neural networks
        Does not create an action for the

        Initializes I/O placeholders used for Tensorflow session runs.
        Initializes and Actor and Critic Network to be used for the purpose of RL.
        """
        #Placeholders
        self.actionSize =actionSize
        self.HPs = HPs
        self.sess=sess
        self.scope=scope
        self.Model = sharedModel
        self.s = tf.placeholder(tf.float32, [None] + stateShape, 'S')
        self.s_next = tf.placeholder(tf.float32, [None] + stateShape, 'S_next')
        self.reward = tf.placeholder(tf.float32, [None, ], 'R')
        self.td_target = tf.placeholder(tf.float32, [None,self.Model.data["DefaultParams"]["SFSize"]], 'TDtarget')

        input = {"state":self.s}
        out = self.Model(input)
        self.state_pred = out["prediction"]
        self.reward_pred = out["reward_pred"]
        self.phi = out["phi"]
        self.psi = out["psi"]

        self.buffer = [Trajectory(depth=7) for _ in range(nTrajs)]

        self.c_params = self.Model.GetVariables("Critic")
        self.s_params = self.Model.GetVariables("Reconstruction")
        self.r_params = self.Model.GetVariables("Reward")

        with tf.name_scope('c_loss'):
            sf_error = tf.subtract(self.td_target, self.psi, name='TD_error')
            sf_error = tf.square(sf_error)
            self.c_loss = tf.reduce_mean(sf_error,name="sf_loss")

        with tf.name_scope('s_loss'):
            if HPs["Loss"] == "MSE":
                self.s_loss = tf.losses.mean_squared_error(self.state_pred,self.s_next)
            elif HPs["Loss"] == "KL":
                self.s_loss = tf.losses.KLD(self.state_pred,self.s_next)
            elif HPs["Loss"] == "M4E":
                self.s_loss = tf.reduce_mean((self.state_pred-self.s_next)**4)

        with tf.name_scope('r_loss'):
            self.r_loss = tf.losses.mean_squared_error(self.reward,tf.squeeze(self.reward_pred))

        if HPs["Optimizer"] == "Adam":
            self.Coptimizer = tf.keras.optimizers.Adam(HPs["Critic LR"])
            self.Soptimizer = tf.keras.optimizers.Adam(HPs["State LR"])
            self.Roptimizer = tf.keras.optimizers.Adam(HPs["Reward LR"])
        elif HPs["Optimizer"] == "RMS":
            self.Coptimizer = tf.keras.optimizers.RMSProp(HPs["Critic LR"])
            self.Soptimizer = tf.keras.optimizers.RMSProp(HPs["State LR"])
            self.Roptimizer = tf.keras.optimizers.RMSProp(HPs["Reward LR"])
        elif HPs["Optimizer"] == "Adagrad":
            self.Coptimizer = tf.keras.optimizers.Adagrad(HPs["Critic LR"])
            self.Soptimizer = tf.keras.optimizers.Adagrad(HPs["State LR"])
            self.Roptimizer = tf.keras.optimizers.Adagrad(HPs["Reward LR"])
        elif HPs["Optimizer"] == "Adadelta":
            self.Coptimizer = tf.keras.optimizers.Adadelta(HPs["Critic LR"])
            self.Soptimizer = tf.keras.optimizers.Adadelta(HPs["State LR"])
            self.Roptimizer = tf.keras.optimizers.Adadelta(HPs["Reward LR"])
        elif HPs["Optimizer"] == "Adamax":
            self.Coptimizer = tf.keras.optimizers.Adamax(HPs["Critic LR"])
            self.Soptimizer = tf.keras.optimizers.Adamax(HPs["State LR"])
            self.Roptimizer = tf.keras.optimizers.Adamax(HPs["Reward LR"])
        elif HPs["Optimizer"] == "Nadam":
            self.Coptimizer = tf.keras.optimizers.Nadam(HPs["Critic LR"])
            self.Soptimizer = tf.keras.optimizers.Nadam(HPs["State LR"])
            self.Roptimizer = tf.keras.optimizers.Nadam(HPs["Reward LR"])
        elif HPs["Optimizer"] == "SGD":
            self.Coptimizer = tf.keras.optimizers.SGD(HPs["Critic LR"])
            self.Soptimizer = tf.keras.optimizers.SGD(HPs["State LR"])
            self.Roptimizer = tf.keras.optimizers.SGD(HPs["Reward LR"])
        elif HPs["Optimizer"] == "Amsgrad":
            self.Coptimizer = tf.keras.optimizers.Adam(HPs["Critic LR"],amsgrad=True)
            self.Soptimizer = tf.keras.optimizers.Adam(HPs["State LR"],amsgrad=True)
            self.Roptimizer = tf.keras.optimizers.Adam(HPs["Reward LR"],amsgrad=True)
        else:
            print("Not selected a proper Optimizer")
            exit()

        with tf.name_scope('local_grad'):
            self.c_grads = self.Coptimizer.get_gradients(self.c_loss, self.c_params)
            self.s_grads = self.Soptimizer.get_gradients(self.s_loss, self.s_params)
            self.r_grads = self.Roptimizer.get_gradients(self.r_loss, self.r_params)

        with tf.name_scope('update'):
            self.update_c_op = self.Coptimizer.apply_gradients(zip(self.c_grads, self.c_params))
            self.update_s_op = self.Soptimizer.apply_gradients(zip(self.s_grads, self.s_params))
            self.update_r_op = self.Roptimizer.apply_gradients(zip(self.r_grads, self.r_params))

        self.update_ops = [self.update_c_op,self.update_s_op,self.update_r_op]
        self.grads = [self.c_grads,self.s_grads,self.r_grads]
        self.losses = [self.c_loss,self.s_loss,self.r_loss]

        self.grad_MA = [MovingAverage(400) for i in range(len(self.grads))]
        self.loss_MA = [MovingAverage(400) for i in range(len(self.grads))]
        self.labels = ["Critic","State","Reward"]

        self.clearBuffer = False

    def GetAction(self, state,episode=0,step=0,deterministic=False,debug=False):
        """
        Contains the code to run the network based on an input.
        """
        s = state[np.newaxis, :]
        phi,psi = self.sess.run([self.phi, self.psi], {self.s: s})   # get probabilities for all actions

        p = 1/self.actionSize
        if len(state.shape)==3:
            probs =np.full((1,self.actionSize),p)
        else:
            probs =np.full((state.shape[0],self.actionSize),p)
        actions = np.array([np.random.choice(probs.shape[1], p=prob / sum(prob)) for prob in probs])

        if debug: print(probs)
        return actions ,[phi,psi]  # return a int and extra data that needs to be fed to buffer.

    def PredictValue(self,state):
        s = state[np.newaxis,:]
        out = self.sess.run(self.value_pred)
        return out
    def PredictState(self,state):
        s = state[np.newaxis,:]
        out = self.sess.run(self.state_pred)
        return out
    def PredictReward(self,state):
        s = state[np.newaxis,:]
        out = self.sess.run(self.reward_pred)
        return out

    def Update(self,episode=0,statistics=True):
        """
        The main update function for A3C. The function pushes gradients to the global AC Network.
        The second function is to Pull
        """
        #Process the data from the buffer
        samples=0
        for i in range(len(self.buffer)):
            samples +=len(self.buffer[i])
        if samples < self.HPs["BatchSize"]:
            return

        for traj in range(len(self.buffer)):

            clip = -1
            td_diff = self.ProcessBuffer(traj,clip)

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
            psi_target = np.array_split(np.squeeze(td_diff),batches)

            for epoch in range(self.HPs["Epochs"]):
                #Create a feedDict from the buffer
                for i in range(batches):
                    feedDict = {
                        self.s: s[i],
                        self.reward: reward[i],
                        self.s_next: s_next[i],
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

        self.ClearTrajectory()


    def GetStatistics(self):
        dict ={}
        for i,label in enumerate(self.labels):
            dict["Training Results/Vanishing Gradient " + label] = self.grad_MA[i]()
            dict["Training Results/Loss " + label] = self.loss_MA[i]()
        return dict


    def ProcessBuffer(self,traj,clip):
        """
        Process the buffer to calculate td_target.

        Parameters
        ----------
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

        td_target, _ = gae(self.buffer[traj][5][:clip], self.buffer[traj][6][:clip], np.zeros_like(self.buffer[traj][5][0]),self.HPs["Gamma"],self.HPs["lambda"])
        # tracker.print_diff()
        return td_target

    # def ClearTrajectory(self):
    #     if self.clearBuffer:
    #         for traj in self.buffer:
    #             traj.clear()
    #         self.clearBuffer=False


    @property
    def getVars(self):
        return self.Model.getVars(self.scope)

    @property
    def getAParams(self):
        return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ 'Actor')

    @property
    def getCParams(self):
        return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=self.Model.scope + '/Shared') + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope=self.Model.scope+ '/Critic')
