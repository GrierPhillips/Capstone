"""Module containing the User class."""

from flask_login import UserMixin
import numpy as np

from . import APP, BCRYPT


class User(UserMixin):
    """Class for managing a user.

    Attributes:
        username (string): User's username.

    """

    def __init__(self, user_doc):
        """Initialize user for given username.

        Args:
            user_doc (dict): Dictionary containing all user attributes.

        """
        self.username = user_doc['Username']
        self.user_id = user_doc['User Id']
        # self.password = user_doc['Password']
        self.email = user_doc['Email']
        self.location = {'City': user_doc['City'], 'State': user_doc['State']}
        self.sub_attrs = {
            'Name Lower': user_doc.get('Name Lower'),
            'Age': user_doc.get('Age'),
            'Gender': user_doc.get('Gender'),
            'Skill': user_doc.get('Skill'),
            'Handicap': user_doc.get('Handicap'),
            'Plays': user_doc.get('Plays'),
            'Reviewed Courses': user_doc.get('Reviewed Courses')
        }

    def get_id(self):
        """Return the username of the User object.

        Returns:
            self.username (string): Current user's username.

        """
        return self.username

    def get_sorted_recs(self):
        """Get user's sorted predicted ratings."""
        recs = APP.config['MODEL'].predict_all(self.user_id)
        recs = np.ma.masked_array(recs, mask=np.zeros(recs.size))
        sorted_recs = recs.argsort()[::-1]
        return sorted_recs
     
    def update(self):
        """Update attributes."""
        updated_doc = APP.config['GRUSERS_COLLECTION']\
            .find_one({'Username': self.username})
        self.location = {
            'City': updated_doc['City'],
            'State': updated_doc['State']
        }
        self.sub_attrs = {
            'Age': updated_doc.get('Age'),
            'Gender': updated_doc.get('Gender'),
            'Skill': updated_doc.get('Skill'),
            'Handicap': updated_doc.get('Handicap'),
            'Plays': updated_doc.get('Plays'),
            'Reviewed Courses': updated_doc.get('Reviewed Courses')
        }

    @classmethod
    def validate_login(cls, password_hash, password):
        """Validate a user's login credentials.

        Args:
            password_hash (string): Hashed password stored in the database.
            password (string): Password entered by user.
        Returns:
            outcome (bool): True if the credentials match, False otherwise.

        """
        outcome = BCRYPT.check_password_hash(password_hash, password)
        return outcome

    @classmethod
    def is_username_taken(cls, username):
        """Check if a username is already in use.

        Args:
            username (string): Username to search collection for.
        Returns:
            taken (bool): True if username is taken, False otherwise.

        """
        taken = APP.config['GRUSERS_COLLECTION']\
            .find({'Name Lower': username}).count() > 0
        return taken

    @classmethod
    def is_email_taken(cls, email):
        """Check if email address is already in use.

        Args:
            email (string): Email address to search collection for.
        Returns:
            taken (bool): True if email is taken, False otherwise.

        """
        taken = APP.config['GRUSERS_COLLECTION']\
            .find({'Email': email}).count() > 0
        return taken
