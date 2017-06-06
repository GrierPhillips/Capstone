"""Module containing the User class."""

from flask_login import UserMixin
from werkzeug.security import check_password_hash

from . import APP


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
        self.name = user_doc['Name']
        self.password = user_doc['Password']
        self.email = user_doc['Email']
        self.location = {'City': user_doc['City'], 'State': user_doc['State']}
        self.sub_attrs = {
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

    @classmethod
    def validate_login(cls, password_hash, password):
        """Validate a user's login credentials.

        Args:
            password_hash (string): Hashed password stored in the database.
            password (string): Password entered by user.
        Returns:
            outcome (bool): True if the credentials match, False otherwise.

        """
        outcome = check_password_hash(password_hash, password)
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
            .find({'Username': username}).count() > 0
        return taken

    @classmethod
    def is_email_taken(self, email):
        """Check if email address is already in use.

        Args:
            email (string): Email address to search collection for.
        Returns:
            taken (bool): True if email is taken, False otherwise.

        """
        taken = APP.config['GRUSERS_COLLECTION']\
            .find({'Email': email}).count() > 0
        return taken