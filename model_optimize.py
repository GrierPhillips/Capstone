import cPickle as pickle
import numpy as np
from sklearn.decomposition import NMF
import matplotlib.pyplot as plt
plt.style.use('fivethirtyeight')



def graph_err():
    '''
    Graph reconstruction_err for values of n_components of NMF from 2-100
    '''
    with open('ratings_mat.pkl', 'r') as f:
        ratings_mat = pickle.load(f)

    err = []
    x = np.arange(2,101)
    for i in x:
        nmf = NMF(n_components=i)
        nmf.fit(ratings_mat)
        err.append(nmf.reconstruction_err_)
        print 'NMF with ', i, 'components fit!'

    recon_err = plt.figure()
    plt.plot(x, err)
    recon_err.show()
