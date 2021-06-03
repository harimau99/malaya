# Copyright 2020 The BigBird Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""BigBird Encoder Layers."""

from . import attention
from . import utils
import tensorflow as tf


class PrenormEncoderLayer(tf.compat.v1.layers.Layer):
    """Encoder layer of a transformer in Pegasus style.

  The layer_norm is taken before self-attention.
  """

    def __init__(
        self,
        attention_type,
        hidden_size=768,
        intermediate_size=3072,
        intermediate_act_fn=utils.gelu,
        attention_probs_dropout_prob=0.0,
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        num_attention_heads=12,
        num_rand_blocks=3,
        block_size=64,
        use_bias=True,
        seed=None,
        name=None,
    ):
        """Constructor of an encoder layer of a transformer in Pegasus style.

    Args:
      attention_type: Type of attention, needs to be one of ['original_full',
        'simulated_sparse', 'block_sparse'].
      hidden_size: (optional) int. Size of hidden dimension.
      intermediate_size: (optional) int. Size of intermediate dimension.
      intermediate_act_fn: optional) Activation function for intermediate layer.
      attention_probs_dropout_prob: (optional) float. Dropout probability of the
        attention probabilities.
      hidden_dropout_prob: (optional) float. Dropout probability of the
        attention.
      initializer_range: (optional) float. Range of the weight initializer.
      num_attention_heads: (optional) int. Number of attention heads.
      num_rand_blocks: (optional) int. Number of random chunks per row.
      block_size: (optional) int. size of block in sequence.
      use_bias: (optional) bool. Whether key/query/value uses a bias vector.
      seed: (Optional) int. Reandom seed for generating random mask.
      name: The name scope of this layer.
    """
        super(PrenormEncoderLayer, self).__init__(name=name)
        self.hidden_dropout_prob = hidden_dropout_prob

        # Attention layer
        attention_head_size = hidden_size // num_attention_heads
        self.attn_layer = attention.MultiHeadedAttentionLayer(
            attention_type,
            num_attention_heads,
            num_rand_blocks,
            attention_head_size,
            initializer_range,
            block_size,
            block_size,
            attention_probs_dropout_prob,
            use_bias,
            seed,
            name='self',
        )

        # Dense layers
        self.projection_layer = utils.Dense3dProjLayer(
            num_attention_heads,
            attention_head_size,
            utils.create_initializer(initializer_range),
            None,
            'dense',
            use_bias,
        )
        self.expand_layer = utils.Dense2dLayer(
            intermediate_size,
            utils.create_initializer(initializer_range),
            intermediate_act_fn,
            'dense',
        )
        self.contract_layer = utils.Dense2dLayer(
            hidden_size,
            utils.create_initializer(initializer_range),
            None,
            'dense',
        )

        # Normalization layer
        self.first_layer_norm = utils.NormLayer()
        self.second_layer_norm = utils.NormLayer()

    @property
    def trainable_weights(self):
        tvar_list = (
            self.attn_layer.trainable_weights
            + self.projection_layer.trainable_weights
            + self.expand_layer.trainable_weights
            + self.contract_layer.trainable_weights
            + self.first_layer_norm.trainable_weights
            + self.second_layer_norm.trainable_weights
        )
        self._trainable_weights = list({v.name: v for v in tvar_list}.values())
        return self._trainable_weights

    def call(
        self,
        layer_input,
        attention_mask=None,
        band_mask=None,
        from_mask=None,
        to_mask=None,
        input_blocked_mask=None,
        training=None,
    ):
        """Implements a encoder layer of a transformer in Pegasus style.

    Args:
      layer_input: float Tensor of shape [batch_size, seq_length, hidden_size].
      attention_mask: (optional) int32 Tensor of shape [batch_size,
        seq_length, seq_length]. The values should be 1 or 0. The
        attention scores will effectively be set to -infinity for any positions
        in the mask that are 0, and will be unchanged for positions that are 1.
      band_mask: (optional) int32 Tensor of shape [batch_size, 1,
        seq_length//block_size-4, block_size, 3*block_size].
        The values should be 1 or 0. The attention scores will effectively be
        set to -infinity for any positions in the mask that are 0, and will be
        unchanged for positions that are 1.
      from_mask: (optional) int32 Tensor of shape [batch_size, 1,
        seq_length, 1]. The values should be 1 or 0. The
        attention scores will effectively be set to -infinity for any positions
        in the mask that are 0, and will be unchanged for positions that are 1.
      to_mask: (optional) int32 Tensor of shape [batch_size, 1, 1,
        seq_length]. The values should be 1 or 0. The
        attention scores will effectively be set to -infinity for any positions
        in the mask that are 0, and will be unchanged for positions that are 1.
      input_blocked_mask: (optional) int32 Tensor of shape [batch_size,
        seq_length//block_size, block_size]. Same as from/to_mask, just
        reshaped.
      training: Boolean indicating whether the call is training or inference.

    Returns:
      float Tensor of shape [batch_size, seq_length, hidden_size].

    Raises:
      ValueError: Any of the arguments or tensor shapes are invalid.
      NotImplementedError: For unknown attention type.
    """

        with tf.compat.v1.variable_scope('attention'):
            with tf.compat.v1.variable_scope('self') as sc:
                normalized_layer_input = self.first_layer_norm(layer_input)
                attention_output = self.attn_layer(
                    normalized_layer_input,
                    normalized_layer_input,
                    attention_mask,
                    band_mask,
                    from_mask,
                    to_mask,
                    input_blocked_mask,
                    input_blocked_mask,
                    training,
                    scope=sc,
                )

            # Run a linear projection of `hidden_size` then add a residual
            # with `layer_input`.
            with tf.compat.v1.variable_scope('output'):
                attention_output = self.projection_layer(attention_output)
                attention_output = utils.dropout(
                    attention_output, self.hidden_dropout_prob, training
                )
                attention_output = attention_output + layer_input

        # The activation is only applied to the "intermediate" hidden layer.
        with tf.compat.v1.variable_scope('intermediate'):
            normalized_attention_output = self.second_layer_norm(
                attention_output
            )
            intermediate_output = self.expand_layer(normalized_attention_output)

        # Down-project back to `hidden_size` then add the residual.
        with tf.compat.v1.variable_scope('output'):
            layer_output = self.contract_layer(intermediate_output)
            layer_output = utils.dropout(
                layer_output, self.hidden_dropout_prob, training
            )
            layer_output = layer_output + attention_output
        return layer_output


class PostnormEncoderLayer(tf.compat.v1.layers.Layer):
    """Encoder layer of a transformer in BERT style.

  The layer_norm is taken after self-attention.
  """

    def __init__(
        self,
        attention_type,
        hidden_size=768,
        intermediate_size=3072,
        intermediate_act_fn=utils.gelu,
        attention_probs_dropout_prob=0.0,
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        num_attention_heads=12,
        num_rand_blocks=3,
        block_size=64,
        use_bias=True,
        seed=None,
        name=None,
    ):
        """Constructor of an encoder layer of a transformer in BERT style.

    Args:
      attention_type: Type of attention, needs to be one of ['original_full',
        'simulated_sparse', 'block_sparse'].
      hidden_size: (optional) int. Size of hidden dimension.
      intermediate_size: (optional) int. Size of intermediate dimension.
      intermediate_act_fn: optional) Activation function for intermediate layer.
      attention_probs_dropout_prob: (optional) float. Dropout probability of the
        attention probabilities.
      hidden_dropout_prob: (optional) float. Dropout probability of the
        attention.
      initializer_range: (optional) float. Range of the weight initializer.
      num_attention_heads: (optional) int. Number of attention heads.
      num_rand_blocks: (optional) int. Number of random chunks per row.
      block_size: (optional) int. size of block in sequence.
      use_bias: (optional) bool. Whether key/query/value uses a bias vector.
      seed: (Optional) int. Reandom seed for generating random mask.
      name: The name scope of this layer.
    """
        super(PostnormEncoderLayer, self).__init__(name=name)
        self.hidden_dropout_prob = hidden_dropout_prob

        # Attention layer
        attention_head_size = hidden_size // num_attention_heads
        self.attn_layer = attention.MultiHeadedAttentionLayer(
            attention_type,
            num_attention_heads,
            num_rand_blocks,
            attention_head_size,
            initializer_range,
            block_size,
            block_size,
            attention_probs_dropout_prob,
            use_bias,
            seed,
            name='self',
        )

        # Dense layers
        self.projection_layer = utils.Dense3dProjLayer(
            num_attention_heads,
            attention_head_size,
            utils.create_initializer(initializer_range),
            None,
            'dense',
            use_bias,
        )
        self.expand_layer = utils.Dense2dLayer(
            intermediate_size,
            utils.create_initializer(initializer_range),
            intermediate_act_fn,
            'dense',
        )
        self.contract_layer = utils.Dense2dLayer(
            hidden_size,
            utils.create_initializer(initializer_range),
            None,
            'dense',
        )

        # Normalization layer
        self.first_layer_norm = utils.NormLayer()
        self.second_layer_norm = utils.NormLayer()

    @property
    def trainable_weights(self):
        tvar_list = (
            self.attn_layer.trainable_weights
            + self.projection_layer.trainable_weights
            + self.expand_layer.trainable_weights
            + self.contract_layer.trainable_weights
            + self.first_layer_norm.trainable_weights
            + self.second_layer_norm.trainable_weights
        )
        self._trainable_weights = list({v.name: v for v in tvar_list}.values())
        return self._trainable_weights

    def call(
        self,
        layer_input,
        attention_mask=None,
        band_mask=None,
        from_mask=None,
        to_mask=None,
        input_blocked_mask=None,
        training=None,
    ):
        """Implements a encoder layer of a transformer in BERT style.

    Args:
      layer_input: float Tensor of shape [batch_size, seq_length, hidden_size].
      attention_mask: (optional) int32 Tensor of shape [batch_size,
        seq_length, seq_length]. The values should be 1 or 0. The
        attention scores will effectively be set to -infinity for any positions
        in the mask that are 0, and will be unchanged for positions that are 1.
      band_mask: (optional) int32 Tensor of shape [batch_size, 1,
        seq_length//block_size-4, block_size, 3*block_size].
        The values should be 1 or 0. The attention scores will effectively be
        set to -infinity for any positions in the mask that are 0, and will be
        unchanged for positions that are 1.
      from_mask: (optional) int32 Tensor of shape [batch_size, 1,
        seq_length, 1]. The values should be 1 or 0. The
        attention scores will effectively be set to -infinity for any positions
        in the mask that are 0, and will be unchanged for positions that are 1.
      to_mask: (optional) int32 Tensor of shape [batch_size, 1, 1,
        seq_length]. The values should be 1 or 0. The
        attention scores will effectively be set to -infinity for any positions
        in the mask that are 0, and will be unchanged for positions that are 1.
      input_blocked_mask: (optional) int32 Tensor of shape [batch_size,
        seq_length//block_size, block_size]. Same as from/to_mask, just
        reshaped.
      training: Boolean indicating whether the call is training or inference.

    Returns:
      float Tensor of shape [batch_size, seq_length, hidden_size].

    Raises:
      ValueError: Any of the arguments or tensor shapes are invalid.
      NotImplementedError: For unknown attention type.
    """

        with tf.compat.v1.variable_scope('attention'):
            with tf.compat.v1.variable_scope('self') as sc:
                attention_output = self.attn_layer(
                    layer_input,
                    layer_input,
                    attention_mask,
                    band_mask,
                    from_mask,
                    to_mask,
                    input_blocked_mask,
                    input_blocked_mask,
                    training,
                    scope=sc,
                )

            # Run a linear projection of `hidden_size` then add a residual
            # with `layer_input`.
            with tf.compat.v1.variable_scope('output'):
                attention_output = self.projection_layer(attention_output)
                attention_output = utils.dropout(
                    attention_output, self.hidden_dropout_prob, training
                )
                attention_output = self.first_layer_norm(
                    attention_output + layer_input
                )

        # The activation is only applied to the "intermediate" hidden layer.
        with tf.compat.v1.variable_scope('intermediate'):
            intermediate_output = self.expand_layer(attention_output)

        # Down-project back to `hidden_size` then add the residual.
        with tf.compat.v1.variable_scope('output'):
            layer_output = self.contract_layer(intermediate_output)
            layer_output = utils.dropout(
                layer_output, self.hidden_dropout_prob, training
            )
            layer_output = self.second_layer_norm(
                layer_output + attention_output
            )
        return layer_output


class EncoderStack(tf.compat.v1.layers.Layer):
    """Transformer encoder stack."""

    def __init__(self, params):
        name = 'encoder'
        super(EncoderStack, self).__init__(name=name)
        self.params = params

        if params['norm_type'] == 'prenorm':
            encoder_class = PrenormEncoderLayer
        elif params['norm_type'] == 'postnorm':
            encoder_class = PostnormEncoderLayer
        else:
            raise NotImplementedError(
                'Norm type {} is not implemented'.format(params['norm_type'])
            )

        # Encoder layers
        self.encoder_layers = [
            encoder_class(  # pylint: disable=g-complex-comprehension
                self.params['attention_type'],
                self.params['hidden_size'],
                self.params['intermediate_size'],
                utils.get_activation(self.params['hidden_act']),
                self.params['attention_probs_dropout_prob'],
                self.params['hidden_dropout_prob'],
                self.params['initializer_range'],
                self.params['num_attention_heads'],
                self.params['num_rand_blocks'],
                self.params['block_size'],
                self.params['use_bias'],
                seed=layer_idx,
                name='layer_%d' % layer_idx,
            )
            for layer_idx in range(self.params['num_hidden_layers'])
        ]

        # Normalization layer
        self.layer_norm = utils.NormLayer()

    @property
    def trainable_weights(self):
        tvar_list = (
            sum([layer.trainable_weights for layer in self.encoder_layers], [])
            + self.layer_norm.trainable_weights
        )
        self._trainable_weights = list({v.name: v for v in tvar_list}.values())
        return self._trainable_weights

    def call(self, encoder_inputs, encoder_inputs_mask, training=None):
        """Return the output of the decoder layer stacks.

    Args:
      encoder_inputs: tensor with shape
        [batch_size, input_length, hidden_size]
      encoder_inputs_mask: Mask for enccoder input. [batch_size, input_length]
      training: Boolean indicating whether the call is training or inference.

    Returns:
      Finaly layer encoder output. float tensor with shape
        [batch_size, input_length, hidden_size]
    """
        encoder_shape = utils.get_shape_list(encoder_inputs, expected_rank=3)
        batch_size = encoder_shape[0]
        encoder_length = encoder_shape[1]

        if self.params['attention_type'] == 'block_sparse':
            # reshape and cast for blocking
            encoder_block_size = self.params['block_size']
            blocked_encoder_mask = tf.reshape(
                encoder_inputs_mask,
                (
                    batch_size,
                    encoder_length // encoder_block_size,
                    encoder_block_size,
                ),
            )
            encoder_from_mask = tf.reshape(
                encoder_inputs_mask, (batch_size, 1, encoder_length, 1)
            )
            encoder_to_mask = tf.reshape(
                encoder_inputs_mask, (batch_size, 1, 1, encoder_length)
            )

            # create band padding
            attention_mask = None
            band_mask = attention.create_band_mask_from_inputs(
                blocked_encoder_mask, blocked_encoder_mask
            )

        else:
            blocked_encoder_mask = None
            encoder_to_mask = None
            encoder_from_mask = None

            attention_mask = attention.create_attention_mask_from_input_mask(
                encoder_inputs_mask, encoder_inputs_mask
            )
            band_mask = None

        # if self.params["use_gradient_checkpointing"]:
        #   encoder_layer = recompute_gradient(encoder_layer)

        if self.params['norm_type'] == 'postnorm':
            encoder_inputs = self.layer_norm(encoder_inputs)

        layer_output = encoder_inputs
        for layer in self.encoder_layers:
            layer_output = layer(
                layer_output,
                attention_mask,
                band_mask,
                encoder_from_mask,
                encoder_to_mask,
                blocked_encoder_mask,
                training,
            )

        if self.params['norm_type'] == 'prenorm':
            layer_output = self.layer_norm(layer_output)

        return layer_output
