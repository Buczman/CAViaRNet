import tensorflow as tf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

data = pd.read_csv('./data/wig.csv').set_index('Data')
data['log_returns'] = data['Zamkniecie'].rolling(2).apply(lambda x: np.log(x[1]/x[0]), raw=True)


dataset = data.loc[(data.index > '2005-01-01')]
dataset = dataset.iloc[:1250]

def univariate_data(dataset, start_index, end_index, history_size, target_size):
    data = []
    labels = []

    start_index = start_index + history_size
    if end_index is None:
        end_index = len(dataset) - target_size

    for i in range(start_index, end_index):
        indices = range(i-history_size, i)
        # Reshape data from (history_size,) to (history_size, 1)
        data.append(np.reshape(dataset[indices], (history_size, 1)))
        labels.append(dataset[i+target_size])
    return np.array(data), np.array(labels)


@tf.function
def caviar_loss(true, var):
    return -1*(float(true < var) - 0.025) * (true - var)

model = tf.keras.Sequential([
    tf.keras.layers.Dense(256, input_shape=(30, 1)),
    tf.keras.layers.SimpleRNN(100),
    tf.keras.layers.Dense(1)
])
model.compile(optimizer='adam', loss=caviar_loss)  # tf.keras.losses.MSE


def reset_weights(model):
    for layer in model.layers:
        if isinstance(layer, tf.keras.Model): #if you're using a model as a layer
            reset_weights(layer) #apply function recursively
            continue

        #where are the initializers?
        if hasattr(layer, 'cell'):
            init_container = layer.cell
        else:
            init_container = layer

        for key, initializer in init_container.__dict__.items():
            if "initializer" not in key: #is this item an initializer?
                  continue #if no, skip it

            # find the corresponding variable, like the kernel or the bias
            if key == 'recurrent_initializer': #special case check
                var = getattr(init_container, 'recurrent_kernel')
            else:
                var = getattr(init_container, key.replace("_initializer", ""))

            var.assign(initializer(var.shape, var.dtype))
            #use the initializer

def predict_rolling(data):
    tf.keras.backend.clear_session()
    reset_weights(model)
    X_train, Y_train = univariate_data(data, 0, None, 30, 0)
    X_test, X_train = X_train[-1], X_train[:-1]
    Y_test, Y_train = Y_train[-1], Y_train[:-1]
    train_univariate = tf.data.Dataset.from_tensor_slices((X_train, Y_train))
    train_univariate = train_univariate.cache().shuffle(10000).batch(256).repeat()

    model.fit(train_univariate, epochs=1,
              steps_per_epoch=1e3)

    return model.predict(np.expand_dims(X_test, axis=0))

dataset['var'] = dataset.log_returns.rolling(1001).apply(predict_rolling)
dataset.to_csv('./data_var.csv')