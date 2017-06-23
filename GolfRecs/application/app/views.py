"""Module with methods for serving different page views."""

import json
from string import punctuation
# from time import time

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from jellyfish import jaro_winkler
import numpy as np

from . import APP, BCRYPT, LM
from .forms import (LoginForm, RegistrationForm, ReviewForm, UpdateProfileForm,
                    RecommendationForm)
from .user import User
from .utils import (do_review, do_update, check_location, get_next_sequence,
                    get_recommendations, get_user, save_model)


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
        if User.is_username_taken(form['username'].data.lower()):
            error = 'This username is already in use.'
            return render_template('signup.html', form=form, error=error)
        if User.is_email_taken(form['email'].data):
            error = 'This email is already in use.'
            return render_template('signup.html', form=form, error=error)
        check_location(form)
        password = BCRYPT.generate_password_hash(form['password'].data)\
            .decode()
        user_doc = {
            'Username': form['username'].data,
            'Name Lower': form['username'].data.lower(),
            'Email': form['email'].data,
            'City': form['city'].data,
            'State': form['state'].data,
            'Password': password
        }
        user_doc.update({'User Id': get_next_sequence('Users')})
        APP.config['GRUSERS_COLLECTION'].insert_one(user_doc)
        user = User(user_doc)
        login_user(user)
        APP.config['MODEL'].add_user(user_doc['User Id'])
        flash('Thanks for registering!')
        save_model()
        return redirect(url_for('account'))
    else:
        error = form.errors
    return render_template('signup.html', form=form, error=error)


@APP.route('/account')
@login_required
def account():
    """Provide the account page."""
    rev_attrs = [
        'Conditions', 'Layout', 'Difficulty', 'Pace', 'Staff', 'Value',
        'Amenities'
    ]
    user_attrs = [
        'Age', 'Gender', 'Skill', 'Plays', 'Handicap', 'City', 'State'
    ]
    user_item, reviews = get_user(current_user.username)
    intersect = set(user_item).intersection(set(user_attrs))
    keys = sorted(intersect, key=user_attrs.index)
    values = [user_item[key] for key in keys]
    course_rats = [
        set(review).intersection(set(rev_attrs)) for review in reviews
    ]
    return render_template(
        'account.html',
        keys=keys,
        values=values,
        reviews=reviews,
        course_rats=course_rats
    )


@APP.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    """Provide the update profile page."""
    form = UpdateProfileForm()
    atts = {
        getattr(form, key).label.text: value
        for key, value in form.data.items() if key != 'csrf_token' and value
    }
    if 'Country' in atts and 'City' not in atts:
        atts['City'] = form.state.data
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
@login_required
def review():
    """Provide the review page."""
    form = ReviewForm()
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
        flash_errors(form)
    return render_template('review.html', form=form)


@APP.route('/_get_suggestions', methods=['GET'])
@login_required
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


@APP.route('/recommend', methods=['POST', 'GET'])
@login_required
def recommend():
    """Provide the user with location based recommendations."""
    form = RecommendationForm()
    # TODO(me): Build model for recommendations based on personal attributes perhaps with pywFM, and use this model if no reviews but attributes are set.
    if not current_user.sub_attrs['Reviewed Courses']:
        flash(
            "It looks like you haven't reviewed any courses yet. Review a " +
            'course or update your profile with your age, gender, skill, ' +
            'handicap, and play frequency and we will be able to start ' +
            'providing you with recommendations.',
            'message'
        )
        return render_template('recommend.html')
    if form.validate_on_submit():
        location = {'Lat': form.lat.data, 'Lng': form.lng.data}
        courses = get_recommendations(location)
        return render_template(
            'recommend.html',
            courses=courses[:10],
            form=form
        )
    elif request.method == 'POST' and not form.validate_on_submit():
        flash(
            'Error: You must select a location from the autocomplete ' +
            'suggestions.',
            'error'
        )
        return render_template('recommend.html', form=form)
    location = APP.config['CITIES_COLLECTION'].find_one(current_user.location)
    courses = get_recommendations(location)
    return render_template(
        'recommend.html',
        courses=courses[:10],
        form=form
    )


def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
