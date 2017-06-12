"""Module with utility methods used by the different views."""

from flask_login import current_user

from . import APP


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
    APP.config['MODEL'].update_user(
        current_user.user_id,
        review_doc['Course Id'],
        review_doc['rating']
    )
    result = APP.config['GRREVIEWS_COLLECTION'].insert_one(review_doc)
    if not result.inserted_id:
        validate = False
        error = 'Woops! It seems there was an error. Please try again.'
        return validate, error
    validate, error = True, None
    return validate, error


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