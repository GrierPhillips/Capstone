"""Initialize pymongo connection for data managment modules."""

from pymongo import MongoClient
import yaml


DATABASE = MongoClient()['GolfRecs']
with open('../secrets.yaml', 'r') as secrets_file:
    SECRETS = yaml.load(secrets_file)
    DB_SECRETS = SECRETS['MongoDB']
DATABASE.authenticate(DB_SECRETS['user'], DB_SECRETS['pass'])
