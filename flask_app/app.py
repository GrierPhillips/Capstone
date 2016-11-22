from flask import Flask, render_template, request, flash, redirect, url_for, session
from wtforms import Form, BooleanField, StringField, PasswordField, validators
import boto3
from boto3.dynamodb.conditions import Key
from flask_login import UserMixin, LoginManager
import os

app = Flask(__name__)
app.debug = True
app.secret_key = os.environ['GOLFRECS_KEY']
login_manager = LoginManager()
login_manager.init_app(app)
dynamo = boto3.resource('dynamodb', region_name='us-west-2')
user_table = dynamo.Table('GR_Users')
review_table = dynamo.Table('GR_Reviews')

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

    dynamo = boto3.resource('dynamodb', region_name='us-west-2')
    user_table = dynamo.Table('GR_Users')
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
    dynamo = boto3.resource('dynamodb', region_name='us-west-2')
    user_table = dynamo.Table('GR_Users')
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
    return render_template('account.html')

def get_user(name):
    user_query = user_table.get_item(Key={'Username': name})
    user_item = user_query['Item']
    reviews = {}
    for course in user_item['Reviewed_Courses'][:10]:
        reviews.add(review_table.get_item(Key={'Course': course, 'Username': name})['Item'])
    rev_attrs = ['Course_Conditions', 'Course_Layout', 'Course_Difficulty', 'Pace_of_Play', 'Staff_Friendliness', 'Value_for_the_Money']
    user_attrs = ['Age', 'Gender', 'Skill', 'Plays', 'Handicap']
    rev_item = query['Item']
    user_item = query['Item']


if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
