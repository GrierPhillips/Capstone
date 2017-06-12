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
from .utils import do_review, do_update, check_location, get_user


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
            user = User(user_doc)
            login_user(user)
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
        # TODO(me): Make new row in ratings and new column in user_feats
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
            current_user.update()
            return redirect(url_for('account', message=message))
    else:
        error = form.errors
    return render_template('update_profile.html', form=form, error=error)


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
            current_user.update()
            return redirect(url_for('account'))
    else:
        error = form.errors
    return render_template('review.html', form=form, error=error)


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