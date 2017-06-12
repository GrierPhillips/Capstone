"""Configuration settings for GoflRecs app."""

from concurrent.futures import ThreadPoolExecutor
import pickle
from string import punctuation

from pymongo import MongoClient
import yaml

# Setup app
with open('secrets.yaml', 'r') as secrets_file:
    SECRETS = yaml.load(secrets_file)
WTF_CSRF_ENABLED = True
SECRET_KEY = SECRETS['GolfRecs']
DEBUG = True

# Setup MongoDB connections
DB_NAME = 'GolfRecs'
DATABASE = MongoClient()[DB_NAME]
DATABASE.authenticate(SECRETS['MongoDB']['user'], SECRETS['MongoDB']['pass'])
USERS_COLLECTION = DATABASE.Users
COURSES_COLLECTION = DATABASE.Courses
REVIEWS_COLLECTION = DATABASE.Reviews
GRUSERS_COLLECTION = DATABASE.GRUsers
GRREVIEWS_COLLECTION = DATABASE.GRReviews
COUNTERS_COLLECTION = DATABASE.Counters
CITIES_COLLECTION = DATABASE.Cities

# Setup multiprocessing
EXECUTOR = ThreadPoolExecutor()

# Setup course list for search
with open('Course Names.pkl', 'rb') as courses:
    COURSES = pickle.load(courses)
COURSES_CLEANED = [
    ''.join(char for char in course.lower() if char not in punctuation)
    for course in COURSES
]

# Load recommendation model
with open('model.pkl', 'rb') as model:
    MODEL = pickle.load(model)
