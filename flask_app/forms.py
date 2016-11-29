from wtforms import Form, StringField, validators, IntegerField, SelectField, TextAreaField

states = ['Alabama','Alaska','Arizona','Arkansas','California','Colorado',
         'Connecticut','Delaware','Florida','Georgia','Hawaii','Idaho',
         'Illinois','Indiana','Iowa','Kansas','Kentucky','Louisiana',
         'Maine' 'Maryland','Massachusetts','Michigan','Minnesota',
         'Mississippi', 'Missouri','Montana','Nebraska','Nevada',
         'New Hampshire','New Jersey','New Mexico','New York',
         'North Carolina','North Dakota','Ohio',
         'Oklahoma','Oregon','Pennsylvania','Rhode Island',
         'South  Carolina','South Dakota','Tennessee','Texas','Utah',
         'Vermont','Virginia','Washington','West Virginia',
         'Wisconsin','Wyoming']
state_choices = [(state, state) for state in states]

class RegistrationForm(Form):
    username = StringField('Username', validators=[validators.Length(min=3, max=25)])
    email = StringField('Email Address', validators=[validators.Length(min=6, max=35)])
    city = SelectField('city', validators=[validators.DataRequired()])
    state = SelectField('state', validators=[validators.DataRequired()])
    password = StringField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('password_confirm', message='Passwords must match')
    ])
    password_confirm = StringField('Repeat Password')

class LoginForm(Form):
    username = StringField('Username', validators=[validators.Length(min=3, max=25)])
    password = StringField('Password', validators=[validators.DataRequired()])

class UpdateProfileForm(Form):
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[('female', 'Female'), ('male', 'Male'), ('none', 'Choose Not To Identify')])
    skill = SelectField('Skill', choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Adavanced')])
    handicap = SelectField('Handicap', choices=[('0-4', '0-4'), ('5-9','5-9'),('10-14','10-14'),('15-19','15-19'),('20-24','20-24'),('25+','25+'),('dont-know', "Don't know")])
    plays = SelectField('Plays', choices=[('once', 'Once a year'),('twice', 'Twice a year'),('four', 'Once every three months'),('twelve', 'Once a month'),('fity-two', 'Once a week'),('fifty-two-plus', 'A few times a week')])
    state = SelectField('State', choices=state_choices)
    city = SelectField('City')

class ReviewForm(Form):
    state = SelectField('State', choices=state_choices, validators=[validators.Required()])
    course = SelectField('Course', validators=[validators.Required()])
    review = TextAreaField('Review')
    rating = SelectField('Rating', validators=[validators.Required()])
    conditions = SelectField('Condition')
    difficulty = SelectField('Difficulty')
    layout = SelectField('Layout')
    pace = SelectField('Pace')
    staff = SelectField('Staff')
    value = SelectField('Value')
    amenities = SelectField('Amenities')

class RecommendationForm(Form):
    state = SelectField('State', choices=state_choices)
    city = SelectField('City')
