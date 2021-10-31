import logging
import os

from routes.video_rule import video_rule_api

FORMAT = '%(asctime)-15s %(module)s:%(lineno)d %(message)s'

logging.basicConfig(format=FORMAT, datefmt='%Y/%m/%d %H:%M:%S')

logger = logging.getLogger()

isDebug = bool(os.getenv('DEBUG', False))

if isDebug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail

from utils.http import json_resp
from utils.exceptions import ClientError, ServerError
from service.user import UserCredential
from utils.VideoManager import video_manager
from utils.flask_sessions import PgSessionInterface

## blueprints
from routes.admin import admin_api
from routes.user import user_api
from routes.home import home_api
from routes.feed import feed_api
from routes.watch import watch_api
from routes.task import task_api
from routes.user_manage import user_manage_api
from routes.announce import announce_api
from routes.web_hook import web_hook_api
from routes.download_manager import download_manager_api

import yaml
import os

# import sentry
from utils.sentry import sentry_wrapper

isDebug = os.getenv('DEBUG', False)


def get_config(key):

    __fr = open('./config/config.yml', 'r')
    __config = yaml.load(__fr)
    return __config[key] if key in __config else None


login_manager = LoginManager()
login_manager.session_protection = 'strong'

app = Flask(__name__)

# update configuration
app.config.update(
    SECRET_KEY=get_config('app_secret_key'),
    SECRET_PASSWORD_SALT=get_config('app_secret_password_salt'),
    MAIL_SERVER=get_config('mail')['mail_server'],
    MAIL_PORT=get_config('mail')['mail_port'],
    MAIL_USE_TLS=get_config('mail')['mail_use_tls'],
    MAIL_USE_SSL=get_config('mail')['mail_use_ssl'],
    MAIL_USERNAME=get_config('mail')['mail_username'],
    MAIL_PASSWORD=get_config('mail')['mail_password'],
    MAIL_DEFAULT_SENDER=get_config('mail')['mail_default_sender'],
    SITE_NAME=get_config('site')['name'],
    SITE_HOST=get_config('site')['host'],
    SITE_PROTOCOL=get_config('site')['protocol']
)

app.session_interface = PgSessionInterface()

base_path = get_config('download')['location']
video_manager.set_base_path(base_path)


@app.errorhandler(ClientError)
def handle_client_exception(error):
    return json_resp(error.to_dict(), error.status)


@app.errorhandler(ServerError)
def handle_server_exception(error):
    return json_resp(error.to_dict(), error.status)


@app.errorhandler(Exception)
def handle_uncaught_exception(error):
    logger.error(error, exc_info=True)
    return json_resp({'message': 'Internal Server Error'}, 500)


app.register_blueprint(admin_api, url_prefix='/api/admin')
app.register_blueprint(user_api, url_prefix='/api/user')
app.register_blueprint(home_api, url_prefix='/api/home')
app.register_blueprint(feed_api, url_prefix='/api/feed')
app.register_blueprint(watch_api, url_prefix='/api/watch')
app.register_blueprint(task_api, url_prefix='/api/task')
app.register_blueprint(user_manage_api, url_prefix='/api/user-manage')
app.register_blueprint(announce_api, url_prefix='/api/announce')
app.register_blueprint(web_hook_api, url_prefix='/api/web-hook')
app.register_blueprint(download_manager_api, url_prefix='/api/download-manager')
app.register_blueprint(video_rule_api, url_prefix='/api/video-rule')

mail = Mail(app)

login_manager.init_app(app)

# init sentry
sentry_wrapper.app_sentry(app)


@login_manager.user_loader
def load_user(user_id):
    return UserCredential.get(user_id)


@login_manager.unauthorized_handler
def unauthorized():
    return json_resp({'message': 'unauthorized access'}, 401)


if __name__ == '__main__':
    app.debug = isDebug
    app.run(host='0.0.0.0')
