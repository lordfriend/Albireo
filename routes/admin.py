# -*- coding: utf-8 -*-
from flask import request, Blueprint
from utils.http import json_resp
import json
from service.admin import admin_service
from service.auth import auth_user
from flask_login import login_required, current_user
from domain.User import User
from utils.exceptions import ClientError
from utils.common import utils


admin_api = Blueprint('bangumi', __name__)


@admin_api.route('/bangumi', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def list_bangumi():
    page = int(request.args.get('page', 1))
    count = int(request.args.get('count', 10))
    sort_field = request.args.get('order_by', 'update_time')
    sort_order = request.args.get('sort', 'desc')
    name = request.args.get('name', None)
    bangumi_type = int(request.args.get('type', -1))
    return admin_service.list_bangumi(page, count=count, sort_field=sort_field, sort_order=sort_order,
                                      name=name,
                                      bangumi_type=bangumi_type)


@admin_api.route('/bangumi', methods=['POST'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def add_bangumi():
    content = request.get_data(True, as_text=True)
    return admin_service.add_bangumi(content, current_user.id)


@admin_api.route('/bangumi/<id>', methods=['PUT'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def update_bangumi(id):
    data = json.loads(request.get_data(True, as_text=True))
    data['dmhy'] = utils.empty_to_none(data, 'dmhy')
    data['acg_rip'] = utils.empty_to_none(data, 'acg_rip')
    data['libyk_so'] = utils.empty_to_none(data, 'libyk_so')
    data['bangumi_moe'] = utils.empty_to_none(data, 'bangumi_moe')
    data['nyaa'] = utils.empty_to_none(data, 'nyaa')
    return admin_service.update_bangumi(id, data)


@admin_api.route('/bangumi/<id>', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def get_bangumi(id):
    return admin_service.get_bangumi(id)


@admin_api.route('/bangumi/<id>', methods=['DELETE'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def delete_bangumi(id):
    return admin_service.delete_bangumi(id)


@admin_api.route('/query', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def search_bangumi():
    name = request.args.get('name', None)
    type = request.args.get('type', 2) # search type = 2 for anime or type = 6 for japanese tv drama series
    offset = request.args.get('offset', 0)
    count = request.args.get('count', 10)
    if name is not None and len(name) > 0:
        return admin_service.search_bangumi(type, name, offset, count)
    else:
        raise ClientError('Name cannot be None', 400)


@admin_api.route('/query/<bgm_id>', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def query_one_bangumi(bgm_id):
    if bgm_id is not None:
        return admin_service.query_bangumi_detail(bgm_id)
    else:
        return json_resp({})


@admin_api.route('/episode', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def episode_list():
    page = int(request.args.get('page', 1))
    count = int(request.args.get('count', 10))
    sort_field = request.args.get('order_by', 'bangumi_id')
    sort_order = request.args.get('sort', 'desc')
    status = request.args.get('status', None)
    return admin_service.list_episode(page, count, sort_field, sort_order, status)


@admin_api.route('/episode', methods=['POST'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def add_episode():
    content = json.loads(request.get_data(True, as_text=True))
    return admin_service.add_episode(content)


# @admin_api.route('/episode/<episode_id>/thumbnail', methods=['PUT'])
# @login_required
# @auth_user(User.LEVEL_ADMIN)
# def episode_thumbnail(episode_id):
#     content = json.loads(request.get_data(True, as_text=True))
#     return admin_service.update_thumbnail(episode_id, content['time'])


@admin_api.route('/episode/<episode_id>', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def get_episode(episode_id):
    return admin_service.get_episode(episode_id)


@admin_api.route('/episode/<episode_id>', methods=['PUT'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def update_episode(episode_id):
    return admin_service.update_episode(episode_id, json.loads(request.get_data(True, as_text=True)))


@admin_api.route('/episode/<episode_id>', methods=['DELETE'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def delete_episode(episode_id):
    return admin_service.delete_episode(episode_id)


@admin_api.route('/video-file', methods=['GET'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def get_episode_video_file_list():
    episode_id = request.args.get('episode_id')
    return admin_service.get_episode_video_file_list(episode_id)


@admin_api.route('/video-file', methods=['POST'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def add_video_file():
    video_dict = json.loads(request.get_data(as_text=True))
    return admin_service.add_video_file(video_dict)


@admin_api.route('/video-file/<video_file_id>', methods=['PUT'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def update_video_file(video_file_id):
    video_dict = json.loads(request.get_data(as_text=True))
    return admin_service.update_video_file(video_file_id, video_dict)


@admin_api.route('/video-file/<video_file_id>', methods=['DELETE'])
@login_required
@auth_user(User.LEVEL_ADMIN)
def delete_video_file(video_file_id):
    return admin_service.delete_video_file(video_file_id)

# @admin_api.route('/episode/<episode_id>/upload', methods=['POST'])
# @login_required
# @auth_user(User.LEVEL_ADMIN)
# def upload_episode(episode_id):
#     if 'file' not in request.files:
#         raise ClientError(ClientError.NOT_VALID_BODY)
#
#     file = request.files['file']
#     if file.filename == '':
#         raise ClientError(ClientError.NOT_VALID_BODY)
#
#     if file:
#         return admin_service.upload_episode(episode_id, file)
