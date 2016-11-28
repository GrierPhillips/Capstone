from flask import Flask, render_template, request, flash, redirect, url_for, session
from wtforms import Form, StringField, validators, IntegerField, SelectField, TextAreaField
import boto3
from boto3.dynamodb.conditions import Key
from flask_login import UserMixin, LoginManager
import os
import cPickle as pickle

app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['GOLFRECS_KEY']
login_manager = LoginManager()
login_manager.init_app(app)
dynamo = boto3.resource('dynamodb', region_name='us-west-2')
user_table = dynamo.Table('GR_Users')
review_table = dynamo.Table('GR_Reviews')
course_table = dynamo.Table('Courses')
# with open('../courses.pkl', 'r') as f:
#     courses = pickle.load(f)
# course_choices = [(courses.index(course), course) for course in sorted(courses)]
states = ['Alabama','Alaska','Arizona','Arkansas','California','Colorado',
         'Connecticut','Delaware','Florida','Georgia','Hawaii','Idaho',
         'Illinois','Indiana','Iowa','Kansas','Kentucky','Louisiana',
         'Maine' 'Maryland','Massachusetts','Michigan','Minnesota',
         'Mississippi', 'Missouri','Montana','Nebraska','Nevada',
         'New Hampshire','New Jersey','New Mexico','New York',
         'North Carolina','North Dakota','Ohio',
         'Oklahoma','Oregon','Pennsylvania','Rhode Island',
         'South  Carolina','South Dakota','Tennessee','Texas','Utah',
         'Vermont','Virginia','Washington','West Virginia',
         'Wisconsin','Wyoming']
state_choices = [(state, state) for state in states]

class RegistrationForm(Form):
    username = StringField('Username', validators=[validators.Length(min=3, max=25)])
    email = StringField('Email Address', validators=[validators.Length(min=6, max=35)])
    password = StringField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('password_confirm', message='Passwords must match')
    ])
    password_confirm = StringField('Repeat Password')

class LoginForm(Form):
    username = StringField('Username', validators=[validators.Length(min=3, max=25)])
    password = StringField('Password', validators=[validators.DataRequired()])

class UpdateProfileForm(Form):
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[('female', 'Female'), ('male', 'Male'), ('none', 'Choose Not To Identify')])
    skill = SelectField('Skill', choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Adavanced')])
    handicap = SelectField('Handicap', choices=[('0-4', '0-4'), ('5-9','5-9'),('10-14','10-14'),('15-19','15-19'),('20-24','20-24'),('25+','25+'),('dont-know', "Don't know")])
    plays = SelectField('Plays', choices=[('once', 'Once a year'),('twice', 'Twice a year'),('four', 'Once every three months'),('twelve', 'Once a month'),('fity-two', 'Once a week'),('fifty-two-plus', 'A few times a week')])

class ReviewForm(Form):
    state = SelectField('State', choices=state_choices)
    city = SelectField('City')
    course = StringField('Course')
    review = TextAreaField('Review')

@app.route('/', methods=['GET'])
def index():
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
        password = request.form['password']
        message = 'Thanks for registering!'
        result, error = do_signup(name, email, password)
        if result == False:
            return redirect(url_for('signup', error=error))
        else:
            return redirect(url_for('login', message=message))
    elif request.method == 'POST':
        form.validate()
        error = form.errors.values()[0][0]
    return render_template('signup.html', form=form, error=error)

def do_signup(name, email, password):
    user = {'Username': name, 'Email': email, 'Password': password}
    with open('../users.pkl', 'r') as f:
        users = pickle.load(f)
    users.append(name)
    user['User_Id'] = users.index(name)
    with open('../users.pkl', 'w') as f:
        pickle.dump(users, f)
    query = user_table.query(KeyConditionExpression=Key('Username').eq(name))
    if query['Count'] == 0:
        user_table.put_item(Item=user)
        return True, None
    else:
        if query['Items'][0]['Username'] == name:
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
    rev_attrs = ['Course_Conditions', 'Course_Layout', 'Course_Difficulty', 'Pace_of_Play', 'Staff_Friendliness', 'Value_for_the_Money']
    user_attrs = ['Age', 'Gender', 'Skill', 'Plays', 'Handicap']
    user_item, reviews = get_user(session['username'].lower())
    atts = True if len(user_item.keys()) > 4 else False
    return render_template('account.html',
                           atts=atts,
                           user_attrs=user_attrs,
                           user_item=user_item,
                           reviews=reviews
                           )

def get_user(name):
    user_query = user_table.get_item(Key={'Username': name})
    user_item = user_query['Item']
    reviews = None
    if 'Reviewed_Courses' not in user_item.keys():
        return user_item, reviews
    else:
        for course in user_item['Reviewed_Courses'][:-11:-1]:
            reviews.append(review_table.get_item(Key={'Course': course, 'Username': name})['Item'])
            reviews[-1]['Course_Name'] = course_table.get_item()
    return user_item, reviews

@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    form = UpdateProfileForm(request.form)
    print request.form.keys()
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
    atts = {'Age': age, 'Gender': gender, 'Skill': skill, 'Handicap': handicap, 'Plays': plays}
    print atts
    if request.method == 'POST':
        message = 'Thanks for updating your profile!'
        result, error = do_update(atts)
        if result == False:
            return redirect(url_for('update_profile', error=error))
        else:
            return redirect(url_for('account', message=message))
    return render_template('update_profile.html', form=form)

def do_update(atts):
    print session['username'].lower()
    name = session['username'].lower()
    user_item = user_table.get_item(Key={'Username': name})['Item']
    user_item.update(atts)
    user_table.put_item(Item=user_item)
    return True, None

@app.route('/review', methods=['GET', 'POST'])
def review():
    form = ReviewForm(request.form)
    form.city.choices = []
    print request.data
    return render_template('review.html', form=form, states=states)


if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
