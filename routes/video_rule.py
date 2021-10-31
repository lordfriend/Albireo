import json

import requests
import yaml
from flask import Blueprint, request
from flask_login import login_required

from domain.User import User
from service.auth import auth_user

video_rule_api = Blueprint('video_rule', __name__)

video_manager_host = yaml.load(open('./config/config.yml', 'r'))['video_manager_url']


@video_rule_api.route('/proxy', methods=['POST'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def video_rule_api_proxy():
    req_data = json.loads(request.get_data(True, as_text=True))
    req_method = req_data['method']
    req_url = video_manager_host + req_data['url']
    if req_method == 'GET':
        params = req_data.get('params')
        return requests.get(req_url, params=params).json()
    elif req_method == 'POST':
        body = req_data.get('body')
        return requests.post(req_url, json=body).json()
    elif req_method == 'PUT':
        body = req_data.get('body')
        return requests.put(req_url, json=body).json()
    elif req_method == 'DELETE':
        params = req_data.get('params')
        return requests.delete(req_url, params=params).json()
