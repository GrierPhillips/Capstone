from flask import Flask, render_template, request, redirect, url_for, session
import boto3
from boto3.dynamodb.conditions import Key
from flask_login import LoginManager
import os
import cPickle as pickle
import json
import geocoder
from math import radians, cos, sin, asin, sqrt
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from forms import RegistrationForm, LoginForm, UpdateProfileForm, ReviewForm, RecommendationForm, states
from time import sleep

app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['GOLFRECS_KEY']
login_manager = LoginManager()
login_manager.init_app(app)
executor = ThreadPoolExecutor(max_workers=2)
dynamo = boto3.resource('dynamodb', region_name='us-west-2')
user_table = dynamo.Table('GR_Users')
review_table = dynamo.Table('GR_Reviews')
course_table = dynamo.Table('Courses')
cities_table = dynamo.Table('Cities')
with open('model.pkl', 'r') as f:
    model = pickle.load(f)
model.fit()
with open('courses.pkl', 'r') as f:
    courses = pickle.load(f)
with open('users.pkl', 'r') as f:
    users = pickle.load(f)
future = None

@app.route('/', methods=['GET'])
def index():
    if session.get('username'):
        global future
        start = True
        try:
            if not future.done():
                print 'get_rex still running'
                start = False
        except:
            print 'get_rex not started'
            start = False
        if start:
            print 'running get_rex'
            future = executor.submit(get_rex, session['username'].lower())
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegistrationForm(request.form)
    if request.args:
        error = request.args.get('error')
    else:
        error = None
    message = None
    if request.method == 'POST' and form.validate():
        name = request.form['username'].lower()
        email = request.form['email'].lower()
        city = request.form['city']
        state = request.form['state']
        if not cities_table.get_item(Key={'State': state, 'City': city})['Item'].get('Coords'):
            site = geocoder.google(city + ', ' + state).latlng
            cities_table.update_item(Key={'State': state, 'City': city},
                                     UpdateExpression='SET Coords = :v',
                                     ExpressionAttributeValues={':v': site})
        password = request.form['password']
        user_item = {'Username': name, 'Email': email, 'City': city, 'State': state, 'Password': password}
        message = 'Thanks for registering!'
        result, error = do_signup(user_item)
        if result == False:
            return redirect(url_for('signup', error=error))
        else:
            return redirect(url_for('login', message=message))
    elif request.method == 'POST':
        form.validate()
        error = form.errors.values()[0][0]
    return render_template('signup.html', form=form, error=error)

def do_signup(user_item):
    users.append(user_item['Username'])
    user_item['User_Id'] = users.index(user_item['Username'])
    with open('../users.pkl', 'w') as f:
        pickle.dump(users, f)
    query = user_table.query(KeyConditionExpression=Key('Username').eq(user_item['Username']))
    if query['Count'] == 0:
        user_table.put_item(Item=user_item)
        return True, None
    else:
        if query['Items'][0]['Username'] == user_item['Username']:
            error = 'Username already exists.'
            return False, error
        else:
            error = 'Account with this email address already exists.'
            return False, error

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    error = None
    if request.method == 'POST' and form.validate():
        name = request.form['username'].lower()
        password = request.form['password']
        result, error = do_login(name, password)
        if result:

            session['username'] = request.form['username']
            return redirect(url_for('index'))
    return render_template('login.html', form=form, error=error)

def do_login(name, password):
    query = user_table.query(KeyConditionExpression=Key('Username').eq(name))
    if query['Count'] == 0:
        error = 'Username {} does not exist'.format(name)
        return False, error
    elif query['Items'][0]['Password'] != password:
        error = 'Incorrect password'
        return False, error
    else:
        return True, None

@app.route('/account')
def account():
    rev_attrs = ['Conditions', 'Layout', 'Difficulty', 'Pace', 'Staff', 'Value', 'Amenities']
    user_attrs = ['Age', 'Gender', 'Skill', 'Plays', 'Handicap', 'City', 'State']
    user_item, reviews = get_user(session['username'].lower())
    atts = True if len(user_item.keys()) > 4 else False
    return render_template('account.html',
                           atts=atts,
                           user_attrs=user_attrs,
                           user_item=user_item,
                           reviews=reviews,
                           rev_attrs= rev_attrs
                           )

def get_user(name):
    user_query = user_table.get_item(Key={'Username': name})
    user_item = user_query['Item']
    reviews = None
    if 'Reviewed_Courses' not in user_item.keys():
        return user_item, reviews
    else:
        reviews = []
        for course in user_item['Reviewed_Courses'][:-11:-1]:
            reviews.append(review_table.get_item(Key={'Course': course, 'Username': name})['Item'])
            print reviews
            # reviews[-1]['Course'] = course_table.get_item()
    return user_item, reviews

@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    form = UpdateProfileForm(request.form)
    if request.args:
        error = request.args.get('error')
    else:
        error = None
    message = None
    age = request.form.get('age')
    gender = request.form.get('gender')
    skill = request.form.get('skill')
    handicap = request.form.get('handicap')
    plays = request.form.get('plays')
    state = request.form.get('state')
    city = request.form.get('city')
    atts = {'Age': age, 'Gender': gender, 'Skill': skill, 'Handicap': handicap, 'Plays': plays, 'State': state, 'City': city}
    if request.method == 'POST':
        if not cities_table.get_item(Key={'State': state, 'City': city})['Item'].get('Coords'):
            site = geocoder.google(city + ', ' + state).latlng
            site = [Decimal(str(item)) for item in site]
            cities_table.update_item(Key={'State': state, 'City': city},
                                     UpdateExpression='SET Coords = :v',
                                     ExpressionAttributeValues={':v': site})
        message = 'Thanks for updating your profile!'
        result, error = do_update(atts)
        if result == False:
            return redirect(url_for('update_profile', error=error))
        else:
            return redirect(url_for('account', message=message))
    return render_template('update_profile.html', form=form, states=states)

def do_update(atts):
    name = session['username'].lower()
    user_item = user_table.get_item(Key={'Username': name})['Item']
    user_item.update(atts)
    user_table.put_item(Item=user_item)
    return True, None

@app.route('/review', methods=['GET', 'POST'])
def review():
    form = ReviewForm(request.form)
    if request.args:
        error = request.args.get('error')
    else:
        error = None
    message = None
    course = request.form.get('course')
    review = request.form.get('review')
    rating = request.form.get('rating')
    conditions = request.form.get('condition')
    difficulty = request.form.get('difficulty')
    layout = request.form.get('layout')
    pace = request.form.get('pace')
    staff = request.form.get('staff')
    value = request.form.get('value')
    amenities = request.form.get('amenities')
    name = session['username'].lower()
    user_id = user_table.get_item(Key={'Username': name})['Item']['User_Id']
    review_item = {'Username': name, 'User_Id': user_id, 'Course': course, 'Review': review, 'Rating': rating, 'Conditions': conditions, 'Difficulty': difficulty, 'Layout': layout, 'Pace': pace, 'Staff': staff, 'Value': value, 'Amenities': amenities}
    if request.method == 'POST':
        # message = 'Thanks for leaving a review!'
        result, error = do_review(review_item)
        if result == False:
            return redirect(url_for('review', error=error))
        else:
            return redirect(url_for('account'))
    elif request.method == 'POST':
        form.validate()
        error = form.errors.values()[0][0]
    return render_template('review.html', form=form, states=states)

def do_review(review_item):
    review_table.put_item(Item=review_item)
    response = user_table.get_item(Key={'Username': review_item['Username']})
    item = response['Item']
    if item.get('Reviewed_Courses'):
        if review_item['Course'] in item['Reviewed_Courses']:
            error = 'You have already reviewed this course'
            return False, error
        else:
            user_table.update_item(
                Key={
                    'Username': review_item['Username']
                },
                UpdateExpression='SET Reviewed_Courses = list_append(Reviewed_Courses, :c)',
                ExpressionAttributeValues={
                    ':c': review_item['Course']
                }
            )
    else:
        user_table.update_item(
            Key={
                'Username': review_item['Username']
            },
            UpdateExpression='SET Reviewed_Courses = :c',
            ExpressionAttributeValues={
                ':c': [review_item['Course']]
            }
        )
    return True, None

@app.route('/_parse_data', methods=['GET'])
def parse_data():
    if request.method == "GET":
        # only need the id we grabbed in my case.
        name = request.args.get('a')
        response = cities_table.query(KeyConditionExpression=Key('State').eq(name))['Items']
        courses = set()
        for item in response:
            courses.update(item['Courses'])
        courses = list(courses)
        # When returning data it has to be jsonify'ed and a list of tuples (id, value) to populate select fields.
        # Example: [('1', 'One'), ('2', 'Two'), ('3', 'Three')]
        # courses = [(course, course) for course in sorted(courses)]
    return json.dumps(sorted(courses))

@app.route('/_get_cities', methods=['GET'])
def get_cities():
    if request.method == "GET":
        # only need the id we grabbed in my case.
        name = request.args.get('a')
        response = cities_table.query(KeyConditionExpression=Key('State').eq(name))['Items']
        cities = []
        for item in response:
            cities.append(item['City'])
    return json.dumps(sorted(cities))

@app.route('/recommend', methods=['POST', 'GET'])
def recommend():
    print request.method
    print future.result()
    form = RecommendationForm(request.form)
    city = request.form.get('city')
    state = request.form.get('state')
    items = None
    error = None
    recommendations, loc = future.result()
    if request.method == 'POST':
        if not state and not city:
            error = 'You must select a city and state'
            return render_template('recommend.html', error=error, items=items, form=form, states=states)
        location = city + ', ' + state
        result = executor(get_rex, session['username'].lower(), location)
        recommendations, loc = result[0], result[1]
        course_links = []
        course_names = []
        images = []
        for rec in recommendations:
            response = course_table.get_item(Key={'Course_Id': rec})['Item']
            if not response.ge('Website'):
                course_links.append(response['Course'])
            else:
                course_links.append(response['Website'])
            course_names.append(response['Name'])
            if not response.get('Images'):
                images.append(None)
            else:
                images.append(response['Images'][0])
        items = {'Names': course_names, 'Links': course_links, 'Images': images, 'Location': loc}
    return render_template('recommend.html', items=items, form=form, states=states, error=error)

def get_rex(name, location=None):
    user_item = user_table.get_item(Key={'Username': name})['Item']
    if not location:
        user_loc = cities_table.get_item(Key={'State': user_item['State'], 'City': user_item['City']})['Item']['Coords']
        loc = user_item['City'] + ', ' + user_item['State']
    else:
        user_loc = geocoder.google(location).latlng
        cities_table.update_item(Key={'State': location.split()})
        loc = location
    user_id = user_item['User_Id']
    if user_id < model.ratings_mat.shape[0]:
        recs = model.top_n_recs(user_id, model.n_items)
        local_recs = get_local_recs(recs, user_loc, 5)
        print local_recs
        return local_recs, loc
    else:
        courses_rated = [courses.index(course) for course in user_item['Reviewed_Courses']]
        print courses_rated
        course_ratings = []
        for course in courses_rated:
            course = courses[course]
            response = review_table.get_item(Key={'Course': course, 'Username': name})
            rating = response['Item']['Rating']
            course_ratings.append(Decimal(rating))
        recs = model.top_n_recs_not_in_mat(courses_rated, course_ratings, model.n_items)
        local_recs = get_local_recs(recs, user_loc, 5)
        print local_recs
        return local_recs, loc

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    mi = 3959 * c
    return mi

def get_local_recs(user_recs, user_loc, n_courses=5):
    local_recs = []
    while len(local_recs)< 5:
        for rec in user_recs:
            course = course_table.get_item(Key={'Course_Id': rec})['Item']
            if not course['Lattitude']:
                site = geocoder.google(course['City'] + ', ' + course['State']).latlng
                course_table.update_item(Key={"Course_Id": rec},
                                         UpdateExpression='SET Lattitude = :lat, Longitude = :lng',
                                         ExpressionAttributeValues={':lat': site[0], ':lng': site[1]})
                course = course_table.get_item(Key={'Course_Id': rec})['Item']
            d = haversine(user_loc[1], user_loc[0], float(course['Lattitude']), float(course['Longitude']))
            if d < 100:
                local_recs.append(rec)
    return local_recs



if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
