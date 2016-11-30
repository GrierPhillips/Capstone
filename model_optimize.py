import cPickle as pickle
import numpy as np
from sklearn.decomposition import NMF
import matplotlib.pyplot as plt
from ItemItemRecommender import ItemItemRecommender
plt.style.use('fivethirtyeight')



def graph_err(start=2, stop=103, step=5):
    '''
    Graph reconstruction_err for values of n_components of NMF from 2-100
    '''
    with open('ratings_mat.pkl', 'r') as f:
        ratings_mat = pickle.load(f)

    err = []
    x = np.arange(start,stop,step)
    for i in x:
        nmf = NMF(n_components=i)
        nmf.fit(ratings_mat)
        err.append(nmf.reconstruction_err_)
        print 'NMF with ', i, 'components fit!'

    recon_err = plt.figure()
    plt.plot(x, err)
    return recon_err

def graph_sim_diff(start=50, stop=501, step=30):
    with open('ratings_mat.pkl', 'r') as f:
        ratings_mat = pickle.load(f)

    diff = []
    x = np.arange(start,stop,step)
    model = ItemItemRecommender(neighborhood_size=start, ratings_mat=ratings_mat)
    model.fit()
    diff.append((model.neighbor_sim[:,-1] - model.neighbor_sim[:,0]).mean())
    for i in x:
        model.neighborhood_size = i
        model._set_neighborhoods()
        diff.append((model.neighbor_sim[:,-1] - model.neighbor_sim[:,0]).mean())
    avg_sim_diff = plt.figure()
    plt.plot(x, diff)
    return avg_sim_diff
