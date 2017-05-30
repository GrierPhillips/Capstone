# from flask import Flask, render_template, request, redirect, url_for, session
# import boto3
# from boto3.dynamodb.conditions import Key
# from flask_login import LoginManager
# import os
# import cPickle as pickle
# import json
# import geocoder
# from math import radians, cos, sin, asin, sqrt
# from decimal import Decimal
# from concurrent.futures import ThreadPoolExecutor
# from forms import RegistrationForm, LoginForm, UpdateProfileForm, ReviewForm, RecommendationForm, states
# import numpy as np
# from scipy.sparse import vstack, lil_matrix
# from urlparse import urljoin
# import yaml

from concurrent.futures import ThreadPoolExecutor
# import pickle

from flask import Flask, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from forms2 import LoginForm, UpdateProfileForm, RegistrationForm
import geocoder
from pymongo import MongoClient
import yaml


APP = Flask(__name__)
CSRF = CSRFProtect(APP)
# APP.debug = True
with open('secrets.yaml', 'r') as yaml_file:
    SECRETS = yaml.load(yaml_file)
APP.secret_key = SECRETS['GolfRecs']
# LOGIN_MANAGER = LoginManger()
# LOGIN_MANAGER.init_app(APP)
EXECUTOR = ThreadPoolExecutor()
# DYNAMO = boto3.resource('dynamodb', region_name='us-west-2')
# GR_USER_TABLE = DYNAMO.Table('GR_Users')
# REVIEW_TABLE = DYNAMO.Table('GR_Reviews')
# COURSE_TABLE = DYNAMO.Table('Courses')
# TODO(Create cities table): Create a table of cities with their coordinates.
# cities_table = DYNAMO.Table('Cities')
# user_table_orig = DYNAMO.Table('Users')
CONN = MongoClient()
CONN.GolfRecs\
    .authenticate(SECRETS['MongoDB']['user'], SECRETS['MongoDB']['password'])
GR_USER_TABLE = CONN.GolfRecs.GRUsers
USER_TABLE_ORIG = CONN.GolfRecs.Users
REVIEW_TABLE = CONN.GolfRecs.Reviews
COURSE_TABLE = CONN.GolfRecs.Courses
CITIES_TABLE = CONN.GolfRecs.Cities
COUNTER_TABLE = CONN.GolfRecs.seq
# with open('model.pkl', 'r') as f:
#     MODEL = pickle.load(f)

# with open('courses.pkl', 'r') as course_file:
#     COURSES = pickle.load(course_file)
# with open('users.pkl', 'r') as user_file:
#     USERS = pickle.load(user_file)
# future = None


@APP.route('/', methods=['GET'])
def index():
    """Render the homepage."""
    # if session.get('username'):
    #     global future
    #     start = True
    #     try:
    #         if not future.done():
    #             print('get_preds still running')
    #             start = False
    #     except:
    #         print('get_preds not started')
    #     if start:
    #         print('running get_preds')
    #         future = EXECUTOR.submit(get_preds, session['username'].lower())
    # return render_template('index.html')
    # if 'username' in session:
    #     if 'reccomendations' not in session:
    #         session['recommendations'] = EXECUTOR\
    #             .submit(get_preds, session['username'].lower())
    return render_template('index.html')


@APP.route('/signup', methods=['GET', 'POST'])
def signup():
    """Provide the signup page."""
    form = RegistrationForm(request.form)
    if request.args:
        error = request.args.get('error')
    else:
        error = None
    message = None
    if form.validate_on_submit():
        name = request.form['username'].lower()
        email = request.form['email'].lower()
        city = request.form['city']
        state = request.form['state']
        if not CITIES_TABLE.find({'City': city, 'State': state}):
            site = geocoder.google(city + ', ' + state)
            city, state = site.city, site.state
            lat, lng = site.latlng
            if not CITIES_TABLE.find({'City': site.city, 'State': site.state}):
                CITIES_TABLE.insert_one(
                    {'City': city, 'State': state, 'Lat': lat, 'Lng': lng}
                )
        password = request.form['password']
        user_doc = {
            'Username': name,
            'Email': email,
            'City': city,
            'State': state,
            'Password': password
        }
        message = 'Thanks for registering!'
        result, error = do_signup(user_doc)
        if not result:
            return redirect(url_for('signup', error=error))
        else:
            return redirect(url_for('login', message=message))
    else:
        error = form.errors
    return render_template('signup.html', form=form, error=error)


def do_signup(user_doc):
    """Create an entry for a new user in the users table.

    Args:
        user_doc (dict): Dictionary of user attributes.

    """
    name_result = GR_USER_TABLE.find_one({'Username': user_doc['Username']})
    email_result = GR_USER_TABLE.find_one({'Email': user_doc['Email']})
    if name_result:
        error = 'Username already exists.'
        return False, error
    elif email_result:
        error = 'Account with thei email address already exists.'
        return False, error
    else:
        user_id = COUNTER_TABLE.find_one_and_update(
            {'_id': 'Users'},
            {'$inc': {'count': 1}}
        )['count']
        user_doc.update({'User Id': user_id})
        GR_USER_TABLE.insert_one(user_doc)
        return True, None


@APP.route('/login', methods=['GET', 'POST'])
def login():
    """Provide the login page."""
    form = LoginForm(request.form)
    error = None
    print(session.items())
    print(APP.secret_key)
    if form.validate_on_submit():
        name = request.form['username'].lower()
        print(name)
        password = request.form['password']
        result, error = do_login(name, password)
        if result:
            session['username'] = request.form['username']
            return render_template('index.html')
    else:
        error = form.errors
    return render_template('login.html', form=form, error=error)


def do_login(name, password):
    """Attempt to find login credentials in user databse.

    Args:
        name (string): Lowercase string of username.
        password (string): Password string.

    """
    name_result = GR_USER_TABLE.find_one({'Username': name})
    pass_result = name_result['Password'] == password
    if not name_result:
        error = 'Username {} does not exist'.format(name)
        return False, error
    elif not pass_result:
        error = 'Incorrect password'
        return False, error
    else:
        return True, None


@APP.route('/signout')
def signout():
    """Sign a user out of the current session."""
    if 'username' not in session:
        return render_template('login.html')
    session.pop('username', None)
    return render_template('index.html')


@APP.route('/account')
def account():
    """Provide the account page."""
    rev_attrs = [
        'Conditions',
        'Layout',
        'Difficulty',
        'Pace',
        'Staff',
        'Value',
        'Amenities'
    ]
    user_attrs = [
        'Age',
        'Gender',
        'Skill',
        'Plays',
        'Handicap',
        'City',
        'State'
    ]
    user_item, reviews = get_user(session['username'].lower())
    atts = True if len(user_item.keys()) > 4 else False
    return render_template(
        'account.html',
        atts=atts,
        user_attrs=user_attrs,
        user_item=user_item,
        reviews=reviews,
        rev_attrs=rev_attrs
    )


def get_user(name):
    """Retrieve profile for given username.

    Args:
        name (string): String representation of username.
    Returns:
        user_doc (dict): Dictionary representation of the users profile.
        reviews (list): List of all reviews by the user.

    """
    user_doc = GR_USER_TABLE.find_one({'Username': name})
    reviewed_courses = user_doc.get('Reviewed Courses')
    if reviewed_courses:
        reviews = REVIEW_TABLE.find(
            {'Username': name, 'Course Id': {'$in': reviewed_courses[:-11:-1]}}
        )
        return user_doc, reviews
    else:
        return user_doc, []
# def get_user(name):
#     user_query = GR_USER_TABLE.get_item(Key={'Username': name})
#     user_item = user_query['Item']
#     user_id = user_item['User_Id']
#     try:
#         user_ratings = MODEL.ratings_mat[user_id]
#     except:
#         make_user_row(model)
#     reviews = None
#     if 'Reviewed_Courses' not in user_item.keys():
#         return user_item, reviews
#     else:
#         reviews = []
#         for course in user_item['Reviewed_Courses'][:-11:-1]:
#             review_item = REVIEW_TABLE.get_item(Key={'Course': course, 'Username': name})['Item']
#             reviews.append(review_item)
#             if MODEL.ratings_mat[user_id, COURSES.index(course)] < 1:
#                 MODEL.ratings_mat[user_id, COURSES.index(course)] = float(review_item['Rating'])
#             print(reviews)
#             # reviews[-1]['Course'] = COURSE_TABLE.get_item()
#     return user_item, reviews
#


@APP.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    """Provide the update profile page."""
    form = UpdateProfileForm(request.form)
    age = request.form.get('age')
    gender = request.form.get('gender')
    skill = request.form.get('skill')
    handicap = request.form.get('handicap')
    plays = request.form.get('plays')
    state = request.form.get('state')
    city = request.form.get('city')
    atts = {
        'Age': age,
        'Gender': gender,
        'Skill': skill,
        'Handicap': handicap,
        'Plays': plays,
        'State': state,
        'City': city
    }
    if form.validate_on_submit():
        # import ipdb; ipdb.set_trace()
        filled = any(
            [value for key, value in form.data.items() if key != 'csrf_token']
        )
        import ipdb; ipdb.set_trace()
        if not filled:
            error = 'Please fill out at least one field before updating.'
            return render_template(
                'update_profile.html',
                form=form,
                error=error
            )
        if form.location.data != '':
            site = geocoder.google('{}, {}'.format(city, state))
        city, state = site.city, site.state
        lat, lng = site.latlng
        if not CITIES_TABLE.find_one({'City': city, 'State': state}):
            CITIES_TABLE.insert_one(
                {
                    'City': city,
                    'State': state,
                    'Lat': lat,
                    'Lng': lng
                }
            )
        message = 'Thanks for updating your profile!'
        result, error = do_update(atts)
        if not result:
            return redirect(url_for('update_profile', error=error))
        else:
            return redirect(url_for('account', message=message))
    else:
        error = form.errors
    return render_template('update_profile.html', form=form, error=error)


@APP.context_processor
def make_options():
    """Create options for SelectField with default disabled."""
    def make_option(option):
        if option.data == '':
            return option(disabled=True)
        else:
            return option
    return dict(make_option=make_option)


def do_update(atts):
    """Update a user's profile with the given attributes.

    Args:
        atts (dict): Dictionary of attributes to update.
    Returns:
        outcome (bool): Boolean of whether or not the update succeeded.
        error (string or None): If outcome is false, a string stating there was
            an error. Otherwise None.

    """
    name = session['username'].lower()
    result = GR_USER_TABLE.find_one_and_update(
        {'Username': name},
        {'$set': {att: value for att, value in atts.items() if value}}
    )
    if not result:
        outcome = False
        error = 'Woops! It seems there was an error. Please try again.'
    else:
        outcome = True
        error = None
    return outcome, error


@APP.route('/review', methods=['GET', 'POST'])
def review():
    form = ReviewForm(request.form)
#
# @APP.route('/review', methods=['GET', 'POST'])
# def review():
#     form = ReviewForm(request.form)
#     if request.args:
#         error = request.args.get('error')
#     else:
#         error = None
#     message = None
#     course = request.form.get('course')
#     review = request.form.get('review')
#     rating = request.form.get('rating')
#     conditions = request.form.get('condition')
#     difficulty = request.form.get('difficulty')
#     layout = request.form.get('layout')
#     pace = request.form.get('pace')
#     staff = request.form.get('staff')
#     value = request.form.get('value')
#     amenities = request.form.get('amenities')
#     name = session['username'].lower()
#     user_id = GR_USER_TABLE.get_item(Key={'Username': name})['Item']['User_Id']
#     review_item = {'Username': name, 'User_Id': user_id, 'Course': course, 'Review': review, 'Rating': rating, 'Conditions': conditions, 'Difficulty': difficulty, 'Layout': layout, 'Pace': pace, 'Staff': staff, 'Value': value, 'Amenities': amenities}
#     if request.method == 'POST':
#         # message = 'Thanks for leaving a review!'
#         result, error = do_review(review_item)
#         if result == False:
#             return redirect(url_for('review', error=error))
#         else:
#             return redirect(url_for('account'))
#     elif request.method == 'POST':
#         form.validate()
#         error = form.errors.values()[0][0]
#     return render_template('review.html', form=form, states=states)
#
# def save_ratings_mat(model):
#     rats = model.ratings_mat
#     with open('ratings_mat.pkl', 'w') as f:
#         pickle.dump(rats, f)
#
# def do_review(review_item):
#     REVIEW_TABLE.put_item(Item=review_item)
#     response = GR_USER_TABLE.get_item(Key={'Username': review_item['Username']})
#     item = response['Item']
#     if item.get('Reviewed_Courses'):
#         if review_item['Course'] in item['Reviewed_Courses']:
#             error = 'You have already reviewed this course'
#             return False, error
#         else:
#             course_id = COURSES.index(review_item['Course'])
#             MODEL.ratings_mat[review_item['User_Id'], course_id] = review_item['Rating']
#             save_ratings_mat(model)
#             GR_USER_TABLE.update_item(
#                 Key={
#                     'Username': review_item['Username']
#                 },
#                 UpdateExpression='SET Reviewed_Courses = list_append(Reviewed_Courses, :c)',
#                 ExpressionAttributeValues={
#                     ':c': review_item['Course']
#                 }
#             )
#     else:
#         GR_USER_TABLE.update_item(
#             Key={
#                 'Username': review_item['Username']
#             },
#             UpdateExpression='SET Reviewed_Courses = :c',
#             ExpressionAttributeValues={
#                 ':c': [review_item['Course']]
#             }
#         )
#     return True, None
#
# @APP.route('/_parse_data', methods=['GET'])
# def parse_data():
#     if request.method == "GET":
#         # only need the id we grabbed in my case.
#         name = request.args.get('a')
#         response = cities_table.query(KeyConditionExpression=Key('State').eq(name))['Items']
#         courses = set()
#         for item in response:
#             courses.update(item['Courses'])
#         courses = list(courses)
#         # When returning data it has to be jsonify'ed and a list of tuples (id, value) to populate select fields.
#         # Example: [('1', 'One'), ('2', 'Two'), ('3', 'Three')]
#         # courses = [(course, course) for course in sorted(courses)]
#     return json.dumps(sorted(courses))
#
# @APP.route('/_get_cities', methods=['GET'])
# def get_cities():
#     if request.method == "GET":
#         # only need the id we grabbed in my case.
#         name = request.args.get('a')
#         response = cities_table.query(KeyConditionExpression=Key('State').eq(name))['Items']
#         cities = []
#         for item in response:
#             cities.append(item['City'])
#     return json.dumps(sorted(cities))
#
# @APP.route('/recommend', methods=['POST', 'GET'])
# def recommend():
#     print(request.method)
#     print(future.result())
#     form = RecommendationForm(request.form)
#     city = request.form.get('city')
#     state = request.form.get('state')
#     items = None
#     error = None
#     recommendations = None
#     loc = None
#     recommendations, loc = future.result()[0], future.result()[1]
#     if request.method == 'POST':
#         if not state and not city:
#             error = 'You must select a city and state'
#             return render_template('recommend.html', error=error, items=items, form=form, states=states)
#         location = city + ', ' + state
#         result = EXECUTOR.submit(get_preds, session['username'].lower(), location)
#         recommendations, loc = result.result()[0], result.result()[1]
#     course_links = []
#     course_names = []
#     images = []
#     for rec in recommendations:
#         response = COURSE_TABLE.get_item(Key={'Course_Id': rec})['Item']
#         if not response.get('Website'):
#             course_links.append(response['Course'])
#         else:
#             course_links.append(urljoin('http://', response['Website']))
#         course_names.append(response['Name'])
#         if not response.get('Images'):
#             images.append('/static/img/no_images.png')
#         else:
#             images.append(response['Images'][0])
#     items = {'Names': course_names, 'Links': course_links, 'Images': images, 'Location': loc}
#     print(items)
#     return render_template('recommend.html', items=items, form=form, states=states, error=error)
#


def get_preds(name):
    """Get predicted ratings for a user.

    Args:
        name (string): Lowercase username to retrieve ratings for.

    """
    user_doc = GR_USER_TABLE.find_one({'Username': name})
    if not user_doc:
        user_doc = USER_TABLE_ORIG.find_one({'Username': name})
    user_id = user_doc['User Id']
    rated = [
        result['Course Id'] for result in REVIEW_TABLE.find({'Username': name})
    ]
    preds = [pred for pred in MODEL.predict_all(user_id) if pred not in rated]
    return preds[:-6:-1]

    # print(name)
    # loc = None
    # try:
    #     user_item = GR_USER_TABLE.get_item(Key={'Username': name})['Item']
    #     print(user_item)
    # except:
    #     user_id = USERS.index(name)
    #     print(user_id)
    #     user_item = USER_TABLE_ORIG.get_item(Key={'User_Id': user_id})['Item']
    #     recs = MODEL.top_n_recs(user_id, MODEL.n_items)
    #     return recs[:-6:-1], loc
    # if location == None:
    #     print('no location entered')
    #     # user_loc = cities_table.get_item(Key={'State': user_item['State'], 'City': user_item['City']})['Item']['Coords']
    #     loc = user_item['City'] + ', ' + user_item['State']
    #     print(loc)
    # else:
    #     site = geocoder.google(location).latlng
    #     site = [Decimal(str(item)) for item in site]
    #     cities_table.update_item(Key={'State': location.split()[0], 'City': location.split()[1]}, UpdateExpression='SET Coords = :v', ExpressionAttributeValues={':v': site})
    #     loc = location
    # user_id = user_item['User_Id']
    # courses_rated = [COURSES.index(course) for course in user_item['Reviewed_Courses']]
    # courses_rated = np.array(courses_rated)
    # print('courses rated', courses_rated)
    # course_ratings = []
    # for course in courses_rated:
    #     course = COURSES[course]
    #     response = REVIEW_TABLE.get_item(Key={'Course': course, 'Username': name})
    #     rating = response['Item']['Rating']
    #     course_ratings.append(float(rating))
    # course_ratings = np.array(course_ratings)
    # recs = MODEL.top_n_recs_not_in_mat(courses_rated, course_ratings, MODEL.n_items)
    # # local_recs = get_local_recs(recs, user_loc, 5)
    # # print 'local recs', local_recs
    # # return local_recs, loc
    # print(recs[:-5])
    # return recs[:-6:-1], loc
#
#
# def haversine(lon1, lat1, lon2, lat2):
#     """Calculate distance between to locations.
#
#     Calculate the great circle distance between two points
#     on the earth (specified in decimal degrees).
#
#     Args:
#         lon1 (float): Float representing longitude of first location.
#         lat1 (flaot): Float representing lattitude of first location.
#         lon2 (float): Float representing longitude of second location.
#         lat2 (flaot): Float representing lattitude of second location.
#     Return:
#         miles (float): Float representing distance between locations.
#     """
#     # convert decimal degrees to radians
#     lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
#     # haversine formula
#     dlon = lon2 - lon1
#     dlat = lat2 - lat1
#     dist_a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
#     dist_c = 2 * asin(sqrt(dist_a))
#     miles = 3959 * dist_c
#     return miles
#
# def get_local_recs(user_recs, user_loc, n_courses=5):
#     local_recs = []
#     # while len(local_recs)< 5:
#     for rec in user_recs:
#         print('Rec # ', rec)
#         course = COURSE_TABLE.get_item(Key={'Course_Id': rec})['Item']
#         if not course['Lattitude']:
#             try:
#                 site = geocoder.google(course['City'] + ', ' + course['State']).latlng
#                 if len(site) == 0:
#                     site = geocoder.google(course['State']).latlng
#                 site = [Decimal(str(item)) for item in site]
#                 print(site)
#                 COURSE_TABLE.update_item(Key={"Course_Id": rec},
#                                          UpdateExpression='SET Lattitude = :lat, Longitude = :lng',
#                                          ExpressionAttributeValues={':lat': site[0], ':lng': site[1]})
#                 course = COURSE_TABLE.get_item(Key={'Course_Id': rec})['Item']
#             except:
#                 continue
#         print(type(course['Lattitude']), type(course['Longitude']))
#         try:
#             d = haversine(user_loc[1], user_loc[0], float(course['Lattitude']), float(course['Longitude']))
#             if d < 1000:
#                 local_recs.append(rec)
#         except:
#             continue
#     return local_recs
#
#
if __name__ == '__main__':
    APP.run(host='0.0.0.0', threaded=True, debug=True)
