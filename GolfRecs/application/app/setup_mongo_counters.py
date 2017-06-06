"""Methods for setting up and retrieving data from a Counter collection."""

from . import APP


DATABASE = APP.config['DATABASE']
USERS = APP.config['USERS_COLLECTION']
COURSES = APP.config['COURSES_COLLECTION']


def setup_counter():
    """Set up the Counter collection."""
    DATABASE.create_collection('Counter')
    counter = DATABASE.Counter
    for user in USERS.find({}).sort('User Id', -1).limit(1):
        max_user = user['User Id']
    for course in COURSES.find({}).sort('Course Id', -1).limit(1):
        max_course = course['Course Id']
    counter.insert({'_id': 'Users', 'seq': max_user})
    counter.insert({'_id': 'Courses', 'seq': max_course})


def get_next_sequence(name):
    """Get the next unique id for a new item in a given collection.

    Args:
        name (string): Name of the collection to retrieve the next unique id
            for.
    Returns:
        next_id (int): Integer value for the next unique id to use.

    """
    seq_doc = DATABASE.Counter.find_and_modify(
        {'_id': name},
        {'$inc': {'seq': 1}},
        new=True
    )
    next_id = seq_doc['seq']
    return next_id
