'''
Train DM Challenge classifier
GPU run command:
    THEANO_FLAGS=mode=FAST_RUN,device=gpu,floatX=float32 python train.py <in:dataset> <out:trained_model>

'''
from __future__ import print_function
import numpy as np
import sys
import tables
import keras.backend as K
from keras.models import Sequential, Model
from keras.layers import Input
from keras.layers.core import Flatten, Dense, Dropout
from keras.layers.convolutional import Convolution2D, MaxPooling2D, ZeroPadding2D
from keras.optimizers import SGD, RMSprop
from keras.applications.vgg16 import VGG16
from sklearn.model_selection import train_test_split
from datetime import datetime

# training parameters
BATCH_SIZE = 10
NB_SMALL = 3000
# NB_EPOCH_SMALL_DATA = 30
NB_EPOCH_SMALL_DATA = 1
NB_EPOCH_LARGE_DATA = 10
# CLASS_WEIGHT = {0: 0.07, 1: 1.0}
CLASS_WEIGHT = {0: 1.0, 1: 1.0}

# dataset
# DATASET_BATCH_SIZE = 1000
DATASET_BATCH_SIZE = 100

# global consts
EXPECTED_SIZE = 224
EXPECTED_CHANNELS = 3
EXPECTED_DIM = (EXPECTED_CHANNELS, EXPECTED_SIZE, EXPECTED_SIZE)
MODEL_PATH = 'weights_{}.h5'.format(datetime.now().strftime('%Y%m%d%H%M%S'))


def dataset_generator(dataset, batch_size):
    while True:
        for i in range(dataset.data.nrows):
            X = dataset.data[i: i + batch_size]
            Y = dataset.labels[i: i + batch_size]
            yield(X, Y)


def confusion(y_true, y_pred):
    y_pred_pos = K.round(K.clip(y_pred, 0, 1))
    y_pred_neg = 1 - y_pred_pos
    y_pos = K.round(K.clip(y_true, 0, 1))
    y_neg = 1 - y_pos
    tp = K.sum(y_pos * y_pred_pos) / K.sum(y_pos)
    tn = K.sum(y_neg * y_pred_neg) / K.sum(y_neg)
    return {'true_pos': tp, 'true_neg': tn}

# command line arguments
dataset_file = sys.argv[1]
model_file = sys.argv[2] if len(sys.argv) > 2 else MODEL_PATH
verbosity = int(sys.argv[3]) if len(sys.argv) > 3 else 1

# loading dataset
print('Loading train dataset: {}'.format(dataset_file))
datafile = tables.open_file(dataset_file, mode='r')
dataset = datafile.root
print(dataset.data[:].shape)

# determine epoch based on data size
if dataset.data[:].shape[0] <= NB_SMALL:
    NB_EPOCH = NB_EPOCH_SMALL_DATA
else:
    NB_EPOCH = NB_EPOCH_LARGE_DATA

# setup model
print('Preparing model')
base_model = VGG16(weights='imagenet', include_top=False, input_tensor=Input(shape=EXPECTED_DIM))
x = base_model.output
x = Flatten()(x)
x = Dense(4096, activation='relu')(x)
x = Dropout(0.5)(x)
x = Dense(4096, activation='relu')(x)
x = Dropout(0.5)(x)
predictions = Dense(1, activation='sigmoid', init='uniform')(x)
# predictions = Dense(1, activation='softmax')(x)

# this is the model we will train
model = Model(input=base_model.input, output=predictions)

# freeze base_model layers
for layer in base_model.layers:
    layer.trainable = False

# compile the model (should be done *after* setting layers to non-trainable)
model.compile(loss='binary_crossentropy', optimizer='sgd', metrics=['accuracy', confusion])
# sgd = SGD(lr=1e-3, decay=1e-6, momentum=0.9, nesterov=True)
# model.compile(optimizer=sgd, loss='binary_crossentropy', metrics=['accuracy'])

# training model
num_rows = dataset.data.nrows
if num_rows > DATASET_BATCH_SIZE:
    # batch training
    model.fit_generator(
        dataset_generator(dataset, BATCH_SIZE),
        samples_per_epoch=num_rows,
        nb_epoch=NB_EPOCH,
        class_weight=CLASS_WEIGHT
    )
    # batch evaluate
    print('Evaluating')
    score = model.evaluate_generator(dataset_generator(dataset, BATCH_SIZE), num_rows)
    print('{}: {}%'.format(model.metrics_names[1], score[1] * 100))

else:
    # one-go training
    X = dataset.data[:]
    Y = dataset.labels[:]
    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.10)
    model.fit(X_train, Y_train,
              batch_size=BATCH_SIZE,
              nb_epoch=NB_EPOCH,
              validation_data=(X_test, Y_test),
              shuffle=True,
              verbose=verbosity,
              class_weight=CLASS_WEIGHT)

    # evaluating
    print('Evaluating')
    score = model.evaluate(X, Y)
    print('{}: {}%'.format(model.metrics_names[1], score[1] * 100))

# saving model
print('Saving model')
# model.save(model_file)
# save weights only to save space
model.save_weights(model_file)

# close dataset
datafile.close()

print('Done.')
