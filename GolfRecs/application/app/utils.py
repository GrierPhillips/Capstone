"""Module with utility methods used by the different views."""

from flask_login import current_user
import numpy as np
from pymongo import UpdateOne

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
        review_doc['Rating']
    )
    result = APP.config['GRREVIEWS_COLLECTION'].insert_one(review_doc)
    APP.config['REVIEWS_COLLECTION'].insert_one(review_doc)
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
    """Check a locations validity and if it exists in the Cities collection.

    Args:
        form (app.forms.RegistrationForm): Registration form containing
            location entered by user.
    """
    city, state, country = form.city.data, form.state.data, form.country.data
    if not city:
        city = form.state.data
        location = APP.config['CITIES_COLLECTION']\
            .find_one({'City': city, 'Country': country})
    else:
        location = APP.config['CITIES_COLLECTION']\
            .find_one({'City': city, 'State': state, 'Country': country})
    if not location:
        lat, lng = form.lat.data, form.lng.data
        loc_doc = {
            'City': city,
            'State': state,
            'Country': country,
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
        reviews = list(APP.config['REVIEWS_COLLECTION'].find({
            'User Id': user_doc['User Id'],
            'Course Id': {'$in': reviewed_courses[:-11:-1]}
        }))
        courses = list(APP.config['COURSES_COLLECTION'].find(
            {'Course Id': {'$in': reviewed_courses[:-11:-1]}}
        ))
        for review_ in reviews:
            review_['Location'] = [
                course['addressLocality'] + ', ' + course['addressRegion']
                for course in courses
                if course['Course Id'] == review_['Course Id']
            ][0]
        return user_doc, reviews
    else:
        return user_doc, []


def get_sorted_index(course_ids, sorted_recs):
    """Return an array of indices to access the sorted recommendations.

    Args:
        course_ids (np.array): Numpy array of course id's returned from mongo.
        sorted_recs (np.array): Numpy array of course id's sorted by
            predicted rating.
    Returns:
        indices (np.array): Numpy array containing the indices of each sorted
            recommendation in course_ids.

    """
    idx = course_ids.argsort()
    sort_x = course_ids[idx]
    sort_idx = np.searchsorted(sort_x, sorted_recs)
    yidx = np.take(idx, sort_idx, mode='clip')
    mask = course_ids[yidx] != sorted_recs
    indices = np.array(np.ma.array(yidx, mask=mask)[~mask])
    return indices


def get_local_courses(loc):
    """Return list of local public courses.

    Args:
        loc (dict): Dictionary containing latitude and longitude for the center
            of the desired sphere.
    Returns:
        local_courses (list of dicts): List of dictionaries containing the
            local course documents.

    """
    coords = {'type': 'Point', 'coordinates': [loc['Lng'], loc['Lat']]}
    sphere = {'$nearSphere': {'$geometry': coords, '$maxDistance': 160934}}
    local_courses = list(
        APP.config['COURSES_COLLECTION'].find(
            {'Private': False, 'location': sphere}
        )
    )
    return local_courses


def get_recommendations(location):
    """Get recommendations for a given user.

    Args:
        location (dict): Dictionary containing central latitude and longitude
        for desired recommendations.
    Returns:
        course_links (dict): Dictionary with course names as keys and links as
            values.

    """
    recs = APP.config['MODEL'].predict_all(current_user.user_id)
    recs = np.ma.masked_array(recs, mask=np.zeros(recs.size))
    sorted_recs = recs.argsort()[::-1]
    # TODO: Find way to store local recs in user object to reduce calls to predict_all()
    local_courses = np.array(get_local_courses(location))
    public_ids = [course['Course Id'] for course in local_courses]
    public_ids = np.array(public_ids)
    course_links = []
    courses = local_courses[get_sorted_index(public_ids, sorted_recs)]
    for course in courses:
        name = course['Name']
        locality, region = course['addressLocality'], course['addressRegion']
        website = course.get('Website')
        if website != '' and website:
            if website.split('//')[0] != 'http:':
                website = 'http://' + website
            course_links.append((name, website, locality, region))
        else:
            course_links.append((name, course['GA Url'], locality, region))
    return course_links


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


def setup_counter():
    """Set up the Counter collection."""
    database = APP.config['DATABASE']
    users = APP.config['USERS_COLLECTION']
    courses = APP.config['COURSES_COLLECTION']
    database.create_collection('Counter')
    counter = database.Counter
    for user in users.find_one(sort=[('User Id', -1)]):
        max_user = user['User Id']
    for course in courses.find_one(sort=[('Course Id', -1)]):
        max_course = course['Course Id']
    counter.insert_one({'_id': 'Users', 'seq': max_user})
    counter.insert_one({'_id': 'Courses', 'seq': max_course})


def get_next_sequence(name):
    """Get the next unique id for a new item in a given collection.

    Args:
        name (string): Name of the collection to retrieve the next unique id
            for.
    Returns:
        next_id (int): Integer value for the next unique id to use.

    """
    counters = APP.config['COUNTERS_COLLECTION']
    seq_doc = counters.find_and_modify(
        {'_id': name},
        {'$inc': {'seq': 1}},
        new=True
    )
    next_id = seq_doc['seq']
    return next_id


def update_reviews():
    """Update the reviews collection.

    Ensures thatscrapped reviews include the correct User Id and Course Id.

    """
    reviews = APP.config['REVIEWS_COLLECTION']
    users = APP.config['USERS_COLLECTION']
    courses = APP.config['COURSES_COLLECTION']
    reviews_cursor = reviews.find(
        {'$or': [
            {'Course Id': {'$exists': False}},
            {'User Id': {'$exists': False}}
        ]}
    )
    updates = []
    for review in reviews_cursor:
        user_id = users.find_one({'Username': review['Username']})['User Id']
        course_id = courses.find_one({'GA Id': review['GA Id']})['Course Id']
        update = UpdateOne(
            {'Review Id': review['Review Id']},
            {'$set': {'Course Id': course_id, 'User Id': user_id}}
        )
        updates.append(update)
    reviews.bulk_write(updates)
