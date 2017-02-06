import numpy as np
import pandas as pd
import scipy.sparse as ss
from sklearn.metrics.pairwise import cosine_similarity
from time import time


class ItemItemRecommender(object):

    def __init__(self, neighborhood_size, ratings_mat):
        self.neighborhood_size = neighborhood_size
        self.ratings_mat = ss.csr_matrix(ratings_mat)
        self.n_users = ratings_mat.shape[0]
        self.n_items = ratings_mat.shape[1]

    def fit(self):
        self.item_sim_mat = cosine_similarity(self.ratings_mat.T)
        self._set_neighborhoods()

    def _set_neighborhoods(self):
        least_to_most_sim_indexes = np.argsort(self.item_sim_mat, 1)
        self.item_sim_mat = ss.csr_matrix(self.item_sim_mat)
        self.neighborhoods = least_to_most_sim_indexes[:, -self.neighborhood_size:]

    def pred_one_user(self, user_id):
        items_rated_by_this_user = self.ratings_mat[user_id].nonzero()[1]
        # Just initializing so we have somewhere to put rating preds
        out = np.zeros(self.n_items)
        for item_to_rate in range(self.n_items):
            relevant_items = np.intersect1d(self.neighborhoods[item_to_rate],
                                            items_rated_by_this_user,
                                            assume_unique=True)  # assume_unique speeds up intersection op

            rel_item = self.item_sim_mat[item_to_rate, relevant_items].data
            rel_sum = self.item_sim_mat[item_to_rate, relevant_items].sum()
            rel_rated = self.ratings_mat[user_id, relevant_items].data
            prod = rel_rated * rel_item
            if prod.shape[0] == 0:
                out[item_to_rate] = 0
                continue
            out[item_to_rate] = prod / rel_sum
        cleaned_out = np.nan_to_num(out)
        return cleaned_out

    def pred_one_user_not_in_mat(self, courses_rated, ratings):
        # Just initializing so we have somewhere to put rating preds
        out = np.zeros(self.n_items)
        for item_to_rate in range(self.n_items):
            relevant_items = np.intersect1d(self.neighborhoods[item_to_rate],courses_rated,assume_unique=True)  # assume_unique speeds up intersection op
            print relevant_items
            relevant_items_index = [np.where(courses_rated == x)[0][0] for x in relevant_items]
            print relevant_items_index, type(relevant_items_index)
            try:
                out[item_to_rate] = ratings[relevant_items_index].dot(self.item_sim_mat[item_to_rate, relevant_items]) / self.item_sim_mat[item_to_rate, relevant_items].sum()
            except:
                # print ratings[relevant_items_index].dot(self.item_sim_mat[item_to_rate, relevant_items]) / self.item_sim_mat[item_to_rate, relevant_items].sum()
                # print ratings[relevant_items_index].dot(self.item_sim_mat[item_to_rate, relevant_items]), self.item_sim_mat[item_to_rate, relevant_items].sum()
                print ratings[relevant_items_index]
                print self.item_sim_mat[item_to_rate, relevant_items]
        cleaned_out = np.nan_to_num(out)
        return cleaned_out

    def pred_all_users(self, report_run_time=False):
        start_time = time()
        all_ratings = [
            self.pred_one_user(user_id) for user_id in range(self.n_users)]
        if report_run_time:
            print("Execution time: %f seconds" % (time()-start_time))
        return np.array(all_ratings)

    def top_n_recs(self, user_id, n):
        pred_ratings = self.pred_one_user(user_id)
        item_index_sorted_by_pred_rating = list(np.argsort(pred_ratings))
        items_rated_by_this_user = self.ratings_mat[user_id].nonzero()[1]
        unrated_items_by_pred_rating = [item for item in item_index_sorted_by_pred_rating
                                        if item not in items_rated_by_this_user]
        return unrated_items_by_pred_rating[-n:]

    def top_n_recs_not_in_mat(self, courses_rated, ratings, n):
        pred_ratings = self.pred_one_user_not_in_mat(courses_rated, ratings)
        item_index_sorted_by_pred_rating = list(np.argsort(pred_ratings))
        items_rated_by_this_user = ratings
        unrated_items_by_pred_rating = [item for item in item_index_sorted_by_pred_rating
                                        if item not in items_rated_by_this_user]
        return unrated_items_by_pred_rating[-n:]
