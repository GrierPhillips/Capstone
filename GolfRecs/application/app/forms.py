"""Module for defining form classes for use in GolfRecs."""

from flask_wtf import FlaskForm
from wtforms import (IntegerField, SelectField, StringField, TextAreaField,
                     HiddenField)
from wtforms.validators import EqualTo, InputRequired, Length, Optional


class LoginForm(FlaskForm):
    """Class for handling login entries."""

    username = StringField(
        'Username',
        validators=[InputRequired(), Length(min=3, max=25)]
    )
    password = StringField(
        'Password',
        validators=[InputRequired(), Length(min=6, max=25)]
    )


class UpdateProfileForm(FlaskForm):
    """Class for handling profile update data."""

    age = IntegerField('Age', validators=[Optional()])
    gender = SelectField(
        'Gender',
        choices=[
            ('', 'Select Gender'),
            ('Female', 'Female'),
            ('Male', 'Male'),
            ('Choose Not to Identify', 'Choose Not To Identify')
        ],
        default='',
        validators=[Optional()]
    )
    skill = SelectField(
        'Skill',
        choices=[
            ('', 'Select Skill'),
            ('Beginner', 'Beginner'),
            ('Intermediate', 'Intermediate'),
            ('Advanced', 'Adavanced')
        ],
        default='',
        validators=[Optional()]
    )
    handicap = SelectField(
        'Handicap',
        choices=[
            ('', 'Select Handicap'),
            ('0-4', '0-4'),
            ('5-9', '5-9'),
            ('10-14', '10-14'),
            ('15-19', '15-19'),
            ('20-24', '20-24'),
            ('25+', '25+'),
            ("Don't Know", "Don't Know")
        ],
        default='',
        validators=[Optional()]
    )
    plays = SelectField(
        'Plays',
        choices=[
            ('', 'Select Play Frequency'),
            ('Once a year', 'Once a year'),
            ('Twice a year', 'Twice a year'),
            ('Once every three months', 'Once every three months'),
            ('Once a month', 'Once a month'),
            ('Once a week', 'Once a week'),
            ('A few times a week', 'A few times a week')
        ],
        default='',
        validators=[Optional()]
    )
    location = StringField('Location', id='location')
    city = HiddenField('City')
    county = HiddenField('County')
    state = HiddenField('State')
    country = HiddenField('Country')
    zip_code = HiddenField('Zip')
    lat = HiddenField('Lat')
    lng = HiddenField('Lng')


class RegistrationForm(FlaskForm):
    """Class for handling registration data."""

    username = StringField(
        'Username',
        validators=[Length(min=3, max=25)]
    )
    email = StringField('Email Address', validators=[Length(min=6, max=35)])
    location = StringField('Location', id='location')
    city = HiddenField('City')
    county = HiddenField('County')
    state = HiddenField('State')
    country = HiddenField('Country')
    zip_code = HiddenField('Zip')
    lat = HiddenField('Lat')
    lng = HiddenField('Lng')
    password = StringField(
        'New Password',
        [
            InputRequired(),
            EqualTo('password_confirm', message='Passwords must match'),
            Length(min=6, max=25)
        ]
    )
    password_confirm = StringField('Repeat Password')


class RecommendationForm(FlaskForm):
    """Class for getting recommendation location."""

    location = StringField('Location', id='location')
    city = HiddenField('City')
    county = HiddenField('County')
    state = HiddenField('State')
    country = HiddenField('Country')
    zip_code = HiddenField('Zip')
    lat = HiddenField('Lat')
    lng = HiddenField('Lng')


class ReviewForm(FlaskForm):
    """Class for handling review submission."""

    rating_range = [(num, num) for num in range(1, 6)]
    course = StringField('Course', validators=[InputRequired()])
    review = TextAreaField('Review')
    rating = SelectField(
        'Rating',
        choices=[('0', 'Rate Course Overall')] + rating_range,
        default='0',
        validators=[InputRequired()],
        coerce=int
    )
    conditions = SelectField(
        'Condition',
        choices=[('', 'Rate Course Conditions')] + rating_range,
        default=''
    )
    difficulty = SelectField(
        'Difficulty',
        choices=[('', 'Rate Course Difficulty')] + rating_range,
        default=''
    )
    layout = SelectField(
        'Layout',
        choices=[('', 'Rate Course Layout')] + rating_range,
        default=''
    )
    pace = SelectField(
        'Pace',
        choices=[('', 'Rate Pace of Play')] + rating_range,
        default=''
    )
    staff = SelectField(
        'Staff',
        choices=[('', 'Rate Staff Friendliness')] + rating_range,
        default=''
    )
    value = SelectField(
        'Value',
        choices=[('', 'Rate Course Value')] + rating_range,
        default=''
    )
    amenities = SelectField(
        'Amenities',
        choices=[('', 'Rate Course Amenities')] + rating_range,
        default=''
    )
