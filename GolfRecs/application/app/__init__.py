"""Initialize the application."""

from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_wtf import CSRFProtect

APP = Flask(__name__)
APP.config.from_object('config')
LM = LoginManager()
LM.init_app(APP)
LM.login_view = 'login'
CSRF = CSRFProtect(APP)
BCRYPT = Bcrypt(APP)

from . import views  # pylint: disable=W0611,C0413; # noqa
