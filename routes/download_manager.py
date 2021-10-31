import json

from flask import Blueprint, request
from flask_login import login_required

from domain.User import User
from service.auth import auth_user
from service.downloader_manager import download_manager_service
from utils.exceptions import ClientError

download_manager_api = Blueprint('download_manager', __name__)


@download_manager_api.route('/job', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def list_jobs():
    status = request.args.get('status')
    if status is None:
        raise ClientError(400)
    else:
        return download_manager_service.get_jobs(status)


@download_manager_api.route('/file-mapping', methods=['POST'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def enhance_file_mapping():
    data = json.loads(request.get_data(True, as_text=True))
    return download_manager_service.enhance_file_mapping(data)
