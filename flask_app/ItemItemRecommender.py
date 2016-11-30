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
        self.neighbor_sim = None

    def fit(self):
        self.item_sim_mat = cosine_similarity(self.ratings_mat.T)
        self._set_neighborhoods()

    def _set_neighborhoods(self):
        least_to_most_sim_indexes = np.argsort(self.item_sim_mat, 1)
        self.neighborhoods = least_to_most_sim_indexes[:, -self.neighborhood_size:]
        self.neighbor_sim = np.zeros(self.n_items * self.neighborhood_size).reshape((self.n_items, self.neighborhood_size))
        for i in xrange(self.n_items):
            self.neighbor_sim[i] = self.item_sim_mat[i, self.neighborhoods[i]]
        self.item_sim_mat = None

    def pred_one_user(self, user_id):
        courses_rated = self.ratings_mat[user_id].nonzero()[1]
        out = np.zeros(self.n_items)
        sim_courses = np.array([])
        for course in courses_rated:
            sim_courses = np.append(sim_courses, self.neighborhoods[course])
        sim_courses = np.unique(sim_courses)
        for i, course in enumerate(sim_courses):
            relevant_items = np.intersect1d(self.neighborhoods[course],
                                            courses_rated,
                                            assume_unique=True)  # assume_unique speeds up intersection op
            out[i] = self.ratings_mat[user_id, relevant_items] * \
                self.neighbor_sim[course, relevant_items] / \
                self.neighbor_sim[course, relevant_items].sum()
        cleaned_out = np.nan_to_num(out)
        return cleaned_out, sim_courses

    def pred_one_user_not_in_mat(self, courses_rated, ratings):
        courses_rated = np.array(courses_rated)
        ratings = np.array(ratings)
        sim_courses = np.array([])
        for course in courses_rated:
            sim_courses = np.append(sim_courses, self.neighborhoods[course])
        sim_courses = np.unique(sim_courses)
        out = np.zeros(len(sim_courses))
        for item in sim_courses:
            index_of_courses = []
            for i, course in enumerate(courses_rated):
                if course in self.neighborhoods[item]:
                    index_of_courses.append(np.where(self.neighbor_sim[item] == course)[0][0])
            out[item] = ratings * self.neighbor_sim[item, index_of_courses] / \
                        self.neighbor_sim[item, index_of_courses].sum()
        cleaned_out = np.nan_to_num(out)
        return cleaned_out, sim_courses

    def pred_all_users(self, report_run_time=False):
        start_time = time()
        all_ratings = [
            self.pred_one_user(user_id) for user_id in range(self.n_users)]
        if report_run_time:
            print("Execution time: %f seconds" % (time()-start_time))
        return np.array(all_ratings)

    def top_n_recs(self, user_id, n):
        pred_ratings, courses = self.pred_one_user(user_id)
        sorted_ratings = np.argsort(pred_ratings)
        courses_by_rating = courses[sorted_ratings]
        courses_rated = self.ratings_mat[user_id].nonzero()[1]
        unrated_courses_sorted_rating = [item for item in courses_by_rating
                                        if item not in courses_rated]
        return unrated_courses_sorted_rating[-n:]

    def top_n_recs_not_in_mat(self, courses_rated, ratings, n):
        pred_ratings, courses = self.pred_one_user_not_in_mat(courses_rated, ratings)
        sorted_ratings = np.argsort(pred_ratings)
        courses_by_rating = courses[sorted_ratings]
        unrated_courses_sorted_rating = [item for item in courses_by_rating
                                        if item not in courses_rated]
        return unrated_courses_sorted_rating[-n:]
