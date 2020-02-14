from tensorflow.keras import backend as K
from tensorflow.keras.layers import Layer
import tensorflow.keras.layers as KL
import numpy as np
from tensorflow.keras.regularizers import l2

class ReverseInception(Layer):
    """Does approximate rounding with Sawtooth wave."""
    def __init__(self,filters=[64,64,32,32],name='inception',**kwargs):
        super(ReverseInception, self).__init__(**kwargs)

        self.inception_1x1 = KL.Conv2DTranspose(filters[0], (1,1), padding='same', activation='relu', name=name+'/1x1', kernel_regularizer=l2(0.0002))
        self.inception_1x1_pad = KL.ZeroPadding2D(padding=(2, 2))

        self.inception_3x3_reduce = KL.Conv2DTranspose(filters[1]//2, (1,1), padding='same', activation='relu', name=name+'/3x3_reduce', kernel_regularizer=l2(0.0002))
        self.inception_3x3_pad = KL.ZeroPadding2D(padding=(1, 1))
        self.inception_3x3 = KL.Conv2DTranspose(filters[1], (3,3), padding='valid', activation='relu', name=name+'/3x3', kernel_regularizer=l2(0.0002))

        self.inception_5x5_reduce = KL.Conv2DTranspose(filters[2]//2, (1,1), padding='same', activation='relu', name=name+'/5x5_reduce', kernel_regularizer=l2(0.0002))
        self.inception_5x5 = KL.Conv2DTranspose(filters[2], (5,5), padding='valid', activation='relu', name=name+'/5x5', kernel_regularizer=l2(0.0002))

        self.inception_pool = KL.MaxPooling2D(pool_size=(3,3), strides=(1,1), padding='same', name=name+'/pool')
        self.inception_pool_pad = KL.ZeroPadding2D(padding=(2, 2))
        self.inception_pool_proj = KL.Conv2DTranspose(filters[3], (1,1), padding='same', activation='relu', name=name+'/pool_proj', kernel_regularizer=l2(0.0002))

        self.inception_output = KL.Concatenate(axis=3, name=name+'/output')


    def call(self, inputs):
        b1 = self.inception_1x1(inputs)
        b1 = self.inception_1x1_pad(b1)

        b2 = self.inception_3x3_reduce(inputs)
        b2 = self.inception_3x3_pad(b2)
        b2 = self.inception_3x3(b2)

        b3 = self.inception_5x5_reduce(inputs)
        # b3 = self.inception_5x5_pad(b3)
        b3 = self.inception_5x5(b3)

        b4 = self.inception_pool(inputs)
        b4 = self.inception_pool_pad(b4)
        b4 = self.inception_pool_proj(b4)

        out = self.inception_output([b1,b2,b3,b4])

        return out

    def compute_output_shape(self, input_shape):
        return input_shape

    def get_config(self):
        config = {}
        base_config = super(ApproxRounding, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))

if __name__ == "__main__":
    from tensorflow.keras.models import Sequential
    import tensorflow as tf
    model=Sequential()
    model.add(ReverseInception())
    x=tf.convert_to_tensor(np.random.random([1,40,40,3]), dtype=tf.float32)
    print(x)
    print(model(x))
