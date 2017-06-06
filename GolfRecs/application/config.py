"""Configuration settings for GoflRecs app."""

from concurrent.futures import ThreadPoolExecutor
import pickle

from pymongo import MongoClient
import yaml


with open('secrets.yaml', 'r') as secrets_file:
    SECRETS = yaml.load(secrets_file)
WTF_CSRF_ENABLED = True
SECRET_KEY = SECRETS['GolfRecs']
DB_NAME = 'GolfRecs'
DATABASE = MongoClient()[DB_NAME]
USERS_COLLECTION = DATABASE.Users
COURSES_COLLECTION = DATABASE.Courses
REVIEWS_COLLECTION = DATABASE.Reviews
GRUSERS_COLLECTION = DATABASE.GRUsers
COUNTERS_COLLECTION = DATABASE.Counters
CITIES_COLLECTION = DATABASE.Cities

EXECUTOR = ThreadPoolExecutor()

with open('Course Names.pkl', 'rb') as courses:
    COURSES = pickle.load(courses)

DEBUG = True
