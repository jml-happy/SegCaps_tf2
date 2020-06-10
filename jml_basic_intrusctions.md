Usage:
A basic test, overfitting on a single image, with minimal console log spam and fast training can be run with:
```python3 ./main.py --net capsbasic --Kfold 1 --aug_data 0 --data_root_dir=data --train```

Author notes
======================================
masks may need to be RGB(A) // same dimensionality as image
    imagemagick batch convert:
        mogrify -define png:format=png32 -type TrueColor data/masks/*.png 
        ( source:  https://github.com/Cheng-Lin-Li/SegCaps/issues/16 )
======================================
Update notes
======================================
TODO: run on:
    coco
    self-made 2D dataset
    self-made 2D hyperspectral dataset
    integrate into research project
    test webcame mode

Modifications:

TF 2.x upgrade (recommend venv 2.2; conda tf 2.1 has memory leak):

Ran google tensorflow 2 upgrade script
Changed shape[i].values to shape[i] throughout
Changed model_summary() function calls to model.summary() class methods
Changed import keras to import tensorflow.keras
    -- except ```from keras.utils.conv_utils import conv_output_length, deconv_length```
        which do not seem to be exposed through the TF 2.2 API

Removed batch_size from tensorboard callback

Fixes:
TODO: manip model model does not work.

Fixed issue with the Kfold=1 / overfitting
Fixed issue with tf.mul getting two differnt types.
    Cast the inpt to weighted_cross_entropy_with_logits in custom losses

Tweaks:

changed default for --loglevel to 0 (least terminal clutter)
    TODO: investigate logging levels and TF specific logging to further reduce and provde options

set args.multiprocessing = False (regardless of platform) for TF 2.2
changed --net default to capsbasic (smallest capsule network model)

Code to calculate steps per epoch based on batch_size, len(train_list), len(val_list)
    - added val_steps_per_epoch argument

    code:
        ```python
         # checks on batch size and checks
        if args.batch_size > len(train_list):
            args.batch_size = len(train_list)

        if args.steps_per_epoch * args.batch_size > len(train_list):
            args.steps_per_epoch = len(train_list) // args.batch_size

        if args.val_steps_per_epoch * args.batch_size > len(val_list):
            args.val_steps_per_epoch = len(val_list) // args.batch_size
        ```

Added comment explaining the tensor reshaping in the ConvCapsuleLayer call method
