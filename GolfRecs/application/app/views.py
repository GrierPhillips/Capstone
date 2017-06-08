"""Module with methods for serving different page views."""

import json
from string import punctuation
# from time import time

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from jellyfish import jaro_winkler
import numpy as np

from . import APP, LM
from .forms import (LoginForm, RegistrationForm, ReviewForm, UpdateProfileForm,
                    RecommendationForm)
from .setup_mongo_counters import get_next_sequence
from .user import User


@APP.route('/', methods=['GET'])
def index():
    """Render the homepage."""
    # if 'username' in session:
    #     if 'reccomendations' not in session:
    #         session['recommendations'] = EXECUTOR\
    #             .submit(get_preds, session['username'].lower())
    return render_template('index.html')


@APP.route('/login', methods=['GET', 'POST'])
def login():
    """Provide the login page."""
    form = LoginForm(request.form)
    error = None
    if form.validate_on_submit():
        user_doc = APP.config['GRUSERS_COLLECTION']\
            .find_one({'Username': form.username.data.lower()})
        valid = User.validate_login(user_doc['Password'], form.password.data)
        if user_doc and valid:
            user_obj = User(user_doc)
            login_user(user_obj)
            flash('User successfully logged in')
            return redirect(request.args.get('next') or url_for('index'))
        elif not valid:
            error = 'Incorrect password for username: {}'\
                .format(form.username.data)
            return render_template('login.html', form=form, error=error)
    else:
        error = form.errors
    return render_template('login.html', form=form, error=error)


@LM.user_loader
def load_user(username):
    """Load a user.

    Args:
        username (string): User's username.
    Returns:
        user_obj (app.user.User): Instance of User class.

    """
    user = APP.config['GRUSERS_COLLECTION'].find_one({'Username': username})
    if not user:
        return None
    user_obj = User(user)
    return user_obj


@APP.route('/signout')
@login_required
def signout():
    """Sign a user out of the current session."""
    logout_user()
    return redirect(url_for('index'))


def check_location(form):
    """Check if a location exists in the Cities collection.

    Args:
        form (app.forms.RegistrationForm): Registration form containing
            location entered by user.
    """
    city, state = form.city.data, form.state.data
    location = APP.config['CITIES_COLLECTION']\
        .find_one({'City': city, 'State': state})
    if not location:
        lat, lng = form.lat.data, form.lng.data
        loc_doc = {
            'City': city,
            'State': state,
            'Lat': lat,
            'Lng': lng
        }
        APP.config['CITIES_COLLECTION'].insert_one(loc_doc)


@APP.route('/signup', methods=['GET', 'POST'])
def signup():
    """Provide the signup page."""
    form = RegistrationForm(request.form)
    if form.validate_on_submit():
        if User.is_username_taken(form['username'].lower()):
            error = 'This username is already in use.'
            return render_template('signup.html', form=form, error=error)
        if User.is_email_taken(form['email']):
            error = 'This email is already in use.'
            return render_template('signup.html', form=form, error=error)
        check_location(form)
        password = form['password']
        user_doc = {
            'Username': form['username'].lower(),
            'Name': form['username'],
            'Email': form['email'],
            'City': form['city'],
            'State': form['state'],
            'Password': password
        }
        user_doc.update({'User Id': get_next_sequence('GRUsers')})
        APP.config['GRUSERS_COLLECTION'].insert_one(user_doc)
        user = User(user_doc)
        login_user(user)
        message = 'Thanks for registering!'
        return redirect(url_for('account', message=message))
    else:
        error = form.errors
    return render_template('signup.html', form=form, error=error)


@APP.route('/account')
@login_required
def account():
    """Provide the account page.

    Args:
        message (string): Message to present to the user.

    """
    rev_attrs = [
        'Conditions', 'Layout', 'Difficulty', 'Pace', 'Staff', 'Value',
        'Amenities'
    ]
    user_attrs = [
        'Age', 'Gender', 'Skill', 'Plays', 'Handicap', 'City', 'State'
    ]
    user_item, reviews = get_user(current_user.username)
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
    user_doc = APP.config['GRUSERS_COLLECTION'].find_one({'Username': name})
    reviewed_courses = user_doc.get('Reviewed Courses')
    if reviewed_courses:
        reviews = APP.config['REVIEWS_COLLECTION'].find(
            {'Username': name, 'Course Id': {'$in': reviewed_courses[:-11:-1]}}
        )
        courses = APP.config['COURSES_COLLECTION'].find(
            {'Course Id': {'$in': reviewed_courses[:-11:-1]}})
        for review_ in reviews:
            review_['Location'] = [
                course['addressLocality'] + ', ' + course['addressRegion']
                for course in courses
                if course['Course Id'] == review_['Course Id']
            ]
        return user_doc, reviews
    else:
        return user_doc, []


@APP.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    """Provide the update profile page."""
    form = UpdateProfileForm()
    atts = {
        getattr(form, key).label.text: value
        for key, value in form.data.items() if key != 'csrf_token'
    }
    if form.validate_on_submit():
        filled = any([value for value in atts.values()])
        if not filled:
            error = 'Please fill out at least one field before updating.'
            return render_template(
                'update_profile.html',
                form=form,
                error=error
            )
        check_location(form)
        message = 'You have successfully updated your profile.'
        result, error = do_update(atts)
        if not result:
            return render_template('update_profile.html', error=error)
        else:
            return redirect(url_for('account', message=message))
    else:
        error = form.errors
    return render_template('update_profile.html', form=form, error=error)


def do_update(atts):
    """Update a user's profile with the given attributes.

    Args:
        atts (dict): Dictionary of attributes to update.
    Returns:
        outcome (bool): Boolean of whether or not the update succeeded.
        error (string or None): If outcome is false, a string stating there was
            an error. Otherwise None.

    """
    result = APP.config['GRUSERS_COLLECTION'].find_one_and_update(
        {'Username': current_user.username},
        {'$set': {attrib: value for attrib, value in atts.items() if value}}
    )
    if not result:
        outcome = False
        error = 'Woops! It seems there was an error. Please try again.'
    else:
        outcome, error = True, None
    return outcome, error


@APP.context_processor
def make_options():
    """Create options for SelectField with default disabled."""
    def make_option(option):
        """Create singe option in SelectField."""
        if option.data == '':
            return option(disabled=True)
        else:
            return option
    return dict(make_option=make_option)


@APP.route('/review', methods=['GET', 'POST'])
def review():
    """Provide the review page."""
    form = ReviewForm()
    if request.args:
        error = request.args.get('error')
    else:
        error = None
    if form.validate_on_submit():
        review_doc = {
            getattr(form, key).label.text: value
            for key, value in form.data.items() if key != 'csrf_token'
            and value
        }
        name, locality = review_doc['Course'].rsplit(', ', 3)[:2]
        course_id = APP.config['COURSES_COLLECTION'].find_one(
            {'Name': name, 'addressLocality': locality}
        )['Course Id']
        review_doc['User Id'] = current_user.user_id
        review_doc['Course Id'] = course_id
        review_doc['Course Name'] = name
        review_doc.pop('Course', None)
        result, error = do_review(review_doc)
        if not result:
            return render_template('review.html', form=form, error=error)
        else:
            return redirect(url_for('account'))
    else:
        error = form.errors
    return render_template('review.html', form=form, error=error)


def do_review(review_doc):
    """Post a review to the Reviews collection.

    Args:
        review_doc (dict): Dictionary containing all review attribues.
    Returns:
        validate (bool): Boolean representing whether the review was valid and
            written or not.
        error (string or None): If validate is False error is a string with an
            error description, otherwise it is None.

    """
    result = APP.config['GRUSERS_COLLECTION'].find_one(
        {'Username': current_user.username})
    if result.get('Reviewed Courses'):
        if review_doc['Course Id'] in result['Reviewed Courses']:
            validate, error = False, 'You have already reviewed this course'
            return validate, error
    APP.config['GRUSERS_COLLECTION'].update_one(
        {'Username': current_user.username},
        {'$addToSet': {'Reviewed Courses': review_doc['Course Id']}}
    )
    # TODO(me): Update ratings matrix with new rating
    result = APP.config['GRREVIEWS_COLLECTION'].insert_one(review_doc)
    if not result.inserted_id:
        validate = False
        error = 'Woops! It seems there was an error. Please try again.'
        return validate, error
    validate, error = True, None
    return validate, error


@APP.route('/_get_suggestions', methods=['GET'])
def get_suggestions():
    """Return the 10 closest entries."""
    courses = APP.config['COURSES_CLEANED']
    text = ''.join(
        char for char in request.args['term'].lower()
        if char not in punctuation
    )
    distances = np.array([
        jaro_winkler(course, text)
        if text not in course else 2 for course in courses
    ])
    top_ten = [
        APP.config['COURSES'][idx] for idx in distances.argsort()[::-1][:10]
    ]
    return json.dumps(list(top_ten))
