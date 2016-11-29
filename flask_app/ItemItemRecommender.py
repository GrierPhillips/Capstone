import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity
from time import time
from sklearn.decomposition import NMF


class ItemItemRecommender(object):

    def __init__(self, neighborhood_size, ratings_mat):
        self.neighborhood_size = neighborhood_size
        self.ratings_mat = ratings_mat
        self.n_users = ratings_mat.shape[0]
        self.n_items = ratings_mat.shape[1]
        self.nmf = NMF(n_components=50)
        self.W = self.nmf.fit_transform(ratings_mat)

    def fit(self):
        self.item_sim_mat = cosine_similarity(self.nmf.components_.T)
        self._set_neighborhoods()

    def _set_neighborhoods(self):
        least_to_most_sim_indexes = np.argsort(self.item_sim_mat, 1)
        self.neighborhoods = least_to_most_sim_indexes[:, -self.neighborhood_size:]

    def pred_one_user(self, user_id, report_run_time=False):
        start_time = time()
        items_rated_by_this_user = self.ratings_mat[user_id].nonzero()[1]
        out = np.zeros(self.n_items)
        for item_to_rate in range(self.n_items):
            relevant_items = np.intersect1d(self.neighborhoods[item_to_rate],
                                            items_rated_by_this_user,
                                            assume_unique=True)  # assume_unique speeds up intersection op
            out[item_to_rate] = self.ratings_mat[user_id, relevant_items] * \
                self.item_sim_mat[item_to_rate, relevant_items] / \
                self.item_sim_mat[item_to_rate, relevant_items].sum()
        if report_run_time:
            print("Execution time: %f seconds" % (time()-start_time))
        cleaned_out = np.nan_to_num(out)
        return cleaned_out

    def pred_user_not_in_mat(self, courses_rated, ratings):
        course_ratings_dict = {course_id: rating for course_id, rating in zip(courses_rated, ratings)}
        print course_ratings_dict
        courses_rated = np.array(courses_rated)
        ratings = np.array(ratings)
        out = np.zeros(self.n_items)
        for item_to_rate in range(self.n_items):
            relevant_items = np.intersect1d(self.neighborhoods[item_to_rate],
                                            courses_rated,
                                            assume_unique=True) # assume_unique speeds up intersection op
            relevant_ratings = np.array([float(course_ratings_dict[key]) for key in relevant_items])
            sim_rel = self.item_sim_mat[item_to_rate, relevant_items]
            rr = relevant_ratings * sim_rel
            rr /= self.item_sim_mat[item_to_rate, relevant_items].sum()
            try:
                out[item_to_rate] = rr
            except:
                out[item_to_rate] = 0
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
        pred_ratings = self.pred_user_not_in_mat(courses_rated, ratings)
        item_index_sorted_by_pred_rating = list(np.argsort(pred_ratings))
        unrated_items_by_pred_rating = [item for item in item_index_sorted_by_pred_rating
                                        if item not in courses_rated]
        return unrated_items_by_pred_rating[-n:]