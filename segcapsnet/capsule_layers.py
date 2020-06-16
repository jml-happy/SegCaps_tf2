'''
Capsules for Object Segmentation (SegCaps)
Original Paper: https://arxiv.org/abs/1804.04241
Code written by: Rodney LaLonde
If you use significant portions of this code or the ideas from our paper, please cite it :)
If you have any questions, please email me at lalonde@knights.ucf.edu.

This file contains the definitions of the various capsule layers and dynamic routing and squashing functions.
'''

import tensorflow.keras.backend as K
import tensorflow as tf
from tensorflow.keras import initializers, layers
from keras.utils.conv_utils import conv_output_length, deconv_length
import numpy as np

class Length(layers.Layer):
    def __init__(self, num_classes, seg=True, **kwargs):
        super(Length, self).__init__(**kwargs)
        if num_classes == 2:
            self.num_classes = 1
        else:
            self.num_classes = num_classes
        self.seg = seg

    def call(self, inputs, **kwargs):
        if inputs.get_shape().ndims == 5:
            assert inputs.get_shape()[-2] == 1, 'Error: Must have num_capsules = 1 going into Length'
            inputs = K.squeeze(inputs, axis=-2)
        return K.expand_dims(tf.norm(tensor=inputs, axis=-1), axis=-1)

    def compute_output_shape(self, input_shape):
        if len(input_shape) == 5:
            input_shape = input_shape[0:-2] + input_shape[-1:]
        if self.seg:
            return input_shape[:-1] + (self.num_classes,)
        else:
            return input_shape[:-1]

    def get_config(self):
        config = {'num_classes': self.num_classes, 'seg': self.seg}
        base_config = super(Length, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class Mask(layers.Layer):
    def __init__(self, resize_masks=False, **kwargs):
        super(Mask, self).__init__(**kwargs)
        self.resize_masks = resize_masks

    def call(self, inputs, **kwargs):
        if type(inputs) is list: # The true label is used to mask the output of capsule layer. For training
            assert len(inputs) == 2
            input, mask = inputs #(?, 512, 512, 1, 16), (?, 512, 512, 1)
            _, hei, wid, _, _ = input.get_shape()
            if self.resize_masks:
                mask = tf.image.resize(mask, (hei, wid), method=tf.image.ResizeMethod.BICUBIC)
            mask = K.expand_dims(mask, -1) #mask = (?, 512, 512, 1, 1)

            # debug color images ###########################################
            # print("\n")
            # print("\nMASK LAYER: input.get_shape().ndims", input.get_shape().ndims)
            # print("MASK LAYER: input.get_shape()", input.get_shape())
            # print("input.shape", input.shape)

            # print("")

            # print("len(input[input): ", len(input))
            # print("len(input[input[0,:]): ", len(input[0,:]))
            # print("len(input[input[0,0,:]): ", len(input[0,0,:]))
            # print("len(input[input[0,0,0,:]): ", len(input[0,0,0,:]))
            # print("len(input[input[0,0,0,0,:]): ", len(input[0,0,0,0,:]))

            # ###
            # print("\n")
            # ###

            # print("MASK LAYER: mask.get_shape().ndims", mask.get_shape().ndims)
            # print("MASK LAYER: mask.get_shape()", mask.get_shape())
            # print("mask.shape", mask.shape)

            # print("")

            # print("len(mask[mask): ", len(mask))
            # print("len(mask[mask[0,:]): ", len(mask[0,:]))
            # print("len(mask[mask[0,0,:]): ", len(mask[0,0,:]))
            # print("len(mask[mask[0,0,0,:]): ", len(mask[0,0,0,:]))
            # print("len(mask[mask[0,0,0,0,:]): ", len(mask[0,0,0,0,:]))
            # print("\n\n")
            # ##############################################################

            if input.get_shape().ndims == 3:
                masked = K.batch_flatten(mask * input)
            else:
                masked = mask * input

        else: # Mask using the capsule with maximal length. For prediction
            if inputs.get_shape().ndims == 3:  # this doesn't happen
                x = K.sqrt(K.sum(K.square(inputs), -1)) #maximal euclidean length
                mask = K.one_hot(indices=K.argmax(x, 1), num_classes=x.get_shape().as_list()[1])
                masked = K.batch_flatten(K.expand_dims(mask, -1) * inputs)
            else:
                masked = inputs

        return masked

    def compute_output_shape(self, input_shape):
    #     print("IN MASK COMPUTE OUTPUT SHAPE:")
    #     print("input_shape: ", input_shape)
    #     print("type(input_shape[0]: ", type(input_shape[0]))
    #     print("input_shape[0]: ", input_shape[0])
        if type(input_shape[0]) is tuple:  # true label provided
            # print("len(input_shape[0]): ", len(input_shape[0]))
            if len(input_shape[0]) == 3:
                return tuple([None, input_shape[0][1] * input_shape[0][2]])
            else:
                return input_shape[0]
        else:  # no true label provided
            if len(input_shape) == 3:
                return tuple([None, input_shape[1] * input_shape[2]])
            else:
                return input_shape

    def get_config(self):
        config = {'resize_masks': self.resize_masks}
        base_config = super(Mask, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class ConvCapsuleLayer(layers.Layer):
    def __init__(self, kernel_size, num_capsule, num_atoms, strides=1, padding='same', routings=3,
                 kernel_initializer='he_normal', **kwargs):
        super(ConvCapsuleLayer, self).__init__(**kwargs)
        self.kernel_size = kernel_size
        self.num_capsule = num_capsule
        self.num_atoms = num_atoms
        self.strides = strides
        self.padding = padding
        self.routings = routings
        self.kernel_initializer = initializers.get(kernel_initializer)

    def build(self, input_shape):
        assert len(input_shape) == 5, "The input Tensor should have shape=[None, input_height, input_width," \
                                      " input_num_capsule, input_num_atoms]"
        self.input_height = input_shape[1]
        self.input_width = input_shape[2]
        self.input_num_capsule = input_shape[3]
        self.input_num_atoms = input_shape[4]

        # Transform matrix
        self.W = self.add_weight(shape=[self.kernel_size, self.kernel_size,
                                 self.input_num_atoms, self.num_capsule * self.num_atoms],
                                 initializer=self.kernel_initializer,
                                 name='W')

        self.b = self.add_weight(shape=[1, 1, self.num_capsule, self.num_atoms],
                                 initializer=initializers.constant(0.1),
                                 name='b')

        self.built = True

    def call(self, input_tensor, training=None):

        input_transposed = tf.transpose(a=input_tensor, perm=[3, 0, 1, 2, 4])
        input_shape = K.shape(input_transposed)

        input_tensor_reshaped = K.reshape(input_transposed, [
            input_shape[0] * input_shape[1], self.input_height, self.input_width, self.input_num_atoms])
        input_tensor_reshaped.set_shape((None, self.input_height, self.input_width, self.input_num_atoms))

        # input tensor:
        # [None, input_height, input_width, input_num_capsule, input_num_atoms]
        # =>
        # convolution is done on a tensor of shape:
        # [num_capsules * batch_size, input_height, input_width, num_atoms]

        # each capsule for each sample essentially becomes as "sample" as interpreted by the cond2d layer
        # num atoms is length of pose vector => number of channel
    
        # comparable to:
        # [num_videos, frames, height, width, RGB]
        # =>
        # [num_videos * frames, height, width, RGB]
        # Question:  would conv3d on 5D tensor be more "sensible/native" ?
        # TODO investigate the correspondence between the set theory and the implementation more deeply.
        conv = K.conv2d(input_tensor_reshaped, self.W, (self.strides, self.strides),
                        padding=self.padding, data_format='channels_last')

        votes_shape = K.shape(conv)
        _, conv_height, conv_width, _ = conv.get_shape()

        votes = K.reshape(conv, [input_shape[1], input_shape[0], votes_shape[1], votes_shape[2],
                                 self.num_capsule, self.num_atoms])
        votes.set_shape((None, self.input_num_capsule, conv_height, conv_width,
                         self.num_capsule, self.num_atoms))

        logit_shape = K.stack([
            input_shape[1], input_shape[0], votes_shape[1], votes_shape[2], self.num_capsule])
        biases_replicated = K.tile(self.b, [conv_height, conv_width, 1, 1])

        activations = update_routing(
            votes=votes,
            biases=biases_replicated,
            logit_shape=logit_shape,
            num_dims=6,
            input_dim=self.input_num_capsule,
            output_dim=self.num_capsule,
            num_routing=self.routings)

        return activations

    def compute_output_shape(self, input_shape):
        space = input_shape[1:-2]
        new_space = []
        for i in range(len(space)):
            new_dim = conv_output_length(
                space[i],
                self.kernel_size,
                padding=self.padding,
                stride=self.strides,
                dilation=1)
            new_space.append(new_dim)

        return (input_shape[0],) + tuple(new_space) + (self.num_capsule, self.num_atoms)

    def get_config(self):
        config = {
            'kernel_size': self.kernel_size,
            'num_capsule': self.num_capsule,
            'num_atoms': self.num_atoms,
            'strides': self.strides,
            'padding': self.padding,
            'routings': self.routings,
            'kernel_initializer': initializers.serialize(self.kernel_initializer)
        }
        base_config = super(ConvCapsuleLayer, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class DeconvCapsuleLayer(layers.Layer):
    def __init__(self, kernel_size, num_capsule, num_atoms, scaling=2, upsamp_type='deconv', padding='same', routings=3,
                 kernel_initializer='he_normal', **kwargs):
        super(DeconvCapsuleLayer, self).__init__(**kwargs)
        self.kernel_size = kernel_size
        self.num_capsule = num_capsule
        self.num_atoms = num_atoms
        self.scaling = scaling
        self.upsamp_type = upsamp_type
        self.padding = padding
        self.routings = routings
        self.kernel_initializer = initializers.get(kernel_initializer)

    def build(self, input_shape):
        assert len(input_shape) == 5, "The input Tensor should have shape=[None, input_height, input_width," \
                                      " input_num_capsule, input_num_atoms]"
        self.input_height = input_shape[1]
        self.input_width = input_shape[2]
        self.input_num_capsule = input_shape[3]
        self.input_num_atoms = input_shape[4]

        # Transform matrix
        if self.upsamp_type == 'subpix':
            self.W = self.add_weight(shape=[self.kernel_size, self.kernel_size,
                                            self.input_num_atoms,
                                            self.num_capsule * self.num_atoms * self.scaling * self.scaling],
                                     initializer=self.kernel_initializer,
                                     name='W')
        elif self.upsamp_type == 'resize':
            self.W = self.add_weight(shape=[self.kernel_size, self.kernel_size,
                                     self.input_num_atoms, self.num_capsule * self.num_atoms],
                                     initializer=self.kernel_initializer, name='W')
        elif self.upsamp_type == 'deconv':
            self.W = self.add_weight(shape=[self.kernel_size, self.kernel_size,
                                            self.num_capsule * self.num_atoms, self.input_num_atoms],
                                     initializer=self.kernel_initializer, name='W')
        else:
            raise NotImplementedError('Upsampling must be one of: "deconv", "resize", or "subpix"')

        self.b = self.add_weight(shape=[1, 1, self.num_capsule, self.num_atoms],
                                 initializer=initializers.constant(0.1),
                                 name='b')

        self.built = True

    def call(self, input_tensor, training=None):
        input_transposed = tf.transpose(a=input_tensor, perm=[3, 0, 1, 2, 4])
        input_shape = K.shape(input_transposed)
        input_tensor_reshaped = K.reshape(input_transposed, [
            input_shape[1] * input_shape[0], self.input_height, self.input_width, self.input_num_atoms])
        input_tensor_reshaped.set_shape((None, self.input_height, self.input_width, self.input_num_atoms))


        if self.upsamp_type == 'resize':
            upsamp = K.resize_images(input_tensor_reshaped, self.scaling, self.scaling, 'channels_last')
            outputs = K.conv2d(upsamp, kernel=self.W, strides=(1, 1), padding=self.padding, data_format='channels_last')
        elif self.upsamp_type == 'subpix':
            conv = K.conv2d(input_tensor_reshaped, kernel=self.W, strides=(1, 1), padding='same',
                            data_format='channels_last')
            outputs = tf.compat.v1.depth_to_space(input=conv, block_size=self.scaling)
        else:
            batch_size = input_shape[1] * input_shape[0]

            # Infer the dynamic output shape:
            out_height = deconv_length(self.input_height, self.scaling, self.kernel_size, self.padding, output_padding=None)
            out_width = deconv_length(self.input_width, self.scaling, self.kernel_size, self.padding, output_padding=None)
            output_shape = (batch_size, out_height, out_width, self.num_capsule * self.num_atoms)

            outputs = K.conv2d_transpose(input_tensor_reshaped, self.W, output_shape, (self.scaling, self.scaling),
                                     padding=self.padding, data_format='channels_last')

        votes_shape = K.shape(outputs)
        _, conv_height, conv_width, _ = outputs.get_shape()

        votes = K.reshape(outputs, [input_shape[1], input_shape[0], votes_shape[1], votes_shape[2],
                                 self.num_capsule, self.num_atoms])
        votes.set_shape((None, self.input_num_capsule, conv_height, conv_width,
                         self.num_capsule, self.num_atoms))

        logit_shape = K.stack([
            input_shape[1], input_shape[0], votes_shape[1], votes_shape[2], self.num_capsule])
        biases_replicated = K.tile(self.b, [votes_shape[1], votes_shape[2], 1, 1])

        activations = update_routing(
            votes=votes,
            biases=biases_replicated,
            logit_shape=logit_shape,
            num_dims=6,
            input_dim=self.input_num_capsule,
            output_dim=self.num_capsule,
            num_routing=self.routings)

        return activations

    def compute_output_shape(self, input_shape):
        output_shape = list(input_shape)

        output_shape[1] = deconv_length(output_shape[1], self.scaling, self.kernel_size, self.padding, output_padding=None)
        output_shape[2] = deconv_length(output_shape[2], self.scaling, self.kernel_size, self.padding, output_padding=None)
        output_shape[3] = self.num_capsule
        output_shape[4] = self.num_atoms

        return tuple(output_shape)

    def get_config(self):
        config = {
            'kernel_size': self.kernel_size,
            'num_capsule': self.num_capsule,
            'num_atoms': self.num_atoms,
            'scaling': self.scaling,
            'padding': self.padding,
            'upsamp_type': self.upsamp_type,
            'routings': self.routings,
            'kernel_initializer': initializers.serialize(self.kernel_initializer)
        }
        base_config = super(DeconvCapsuleLayer, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


def update_routing(votes, biases, logit_shape, num_dims, input_dim, output_dim,
                    num_routing):
    if num_dims == 6:
        votes_t_shape = [5, 0, 1, 2, 3, 4]
        r_t_shape = [1, 2, 3, 4, 5, 0]
    elif num_dims == 4:
        votes_t_shape = [3, 0, 1, 2]
        r_t_shape = [1, 2, 3, 0]
    else:
        raise NotImplementedError('Not implemented')

    votes_trans = tf.transpose(a=votes, perm=votes_t_shape)
    _, _, _, height, width, caps = votes_trans.get_shape()

    def _body(i, logits, activations):
        """Routing while loop."""
        # route: [batch, input_dim, output_dim, ...]
        route = tf.nn.softmax(logits, axis=-1)
        preactivate_unrolled = route * votes_trans
        preact_trans = tf.transpose(a=preactivate_unrolled, perm=r_t_shape)
        preactivate = tf.reduce_sum(input_tensor=preact_trans, axis=1) + biases
        activation = _squash(preactivate)
        activations = activations.write(i, activation)
        act_3d = K.expand_dims(activation, 1)
        tile_shape = np.ones(num_dims, dtype=np.int32).tolist()
        tile_shape[1] = input_dim
        act_replicated = tf.tile(act_3d, tile_shape)
        distances = tf.reduce_sum(input_tensor=votes * act_replicated, axis=-1)
        logits += distances
        return (i + 1, logits, activations)

    activations = tf.TensorArray(
      dtype=tf.float32, size=num_routing, clear_after_read=False)
    logits = tf.fill(logit_shape, 0.0)

    i = tf.constant(0, dtype=tf.int32)
    _, logits, activations = tf.while_loop(
      cond=lambda i, logits, activations: i < num_routing,
      body=_body,
      loop_vars=[i, logits, activations],
      swap_memory=True)

    return K.cast(activations.read(num_routing - 1), dtype='float32')


def _squash(input_tensor):
    norm = tf.norm(tensor=input_tensor, axis=-1, keepdims=True)
    norm_squared = norm * norm
    return (input_tensor / norm) * (norm_squared / (1 + norm_squared))
