# from functools import wraps
from twisted.web import server, resource
from twisted.internet import reactor, endpoints, threads

from utils.SessionManager import SessionManager
from utils.db import row2dict
from domain.Favorites import Favorites
from domain.WebHookToken import WebHookToken
from domain.WebHook import WebHook
from domain.Episode import Episode
from domain.Bangumi import Bangumi
from utils.common import utils
from sqlalchemy.orm import joinedload
from web_hook.events import UserFavoriteEvent, EpisodeEvent, InitialEvent, TokenAddedEvent, UserEmailChangeEvent, \
    TokenRemovedEvent
from web_hook.dispatcher import dispatcher
import logging
import yaml
import urllib


logger = logging.getLogger(__name__)

rpc_exported_dict = {}


def rpc_export(f):
    func_name = f.__name__
    rpc_exported_dict[func_name] = f
    print func_name
    print rpc_exported_dict
    # @wraps(f)
    # def wrapper(*args, **kwargs):
    #     return f(*args, **kwargs)
    return f


class RPCInterface(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        rpc_method = request.path[1:]
        rpc_method_args = {}
        for key in request.args:
            rpc_method_args[key] = request.args[key][0]
        if rpc_method in rpc_exported_dict:
            rpc_exported_dict[rpc_method](**rpc_method_args)
        else:
            print('no such a method ({0}) found'.format(rpc_method,))
        return ''


def setup_server():
    config = yaml.load(open('./config/config.yml', 'r'))
    server_port = 8080
    if 'rpc' in config:
        server_port = config['rpc']['server_port']

    site = server.Site(RPCInterface())
    endpoint = endpoints.TCP4ServerEndpoint(reactor, server_port)
    endpoint.listen(site)


@rpc_export
def user_favorite_update(user_id):

    def query_user_favorite():
        session = SessionManager.Session()
        try:
            web_hook_token_list = session.query(WebHookToken).\
                filter(WebHookToken.user_id == user_id).\
                all()

            favorite_list = session.query(Favorites).\
                filter(Favorites.user_id == user_id).\
                all()

            token_fav_dict = {}
            for web_hook_token in web_hook_token_list:
                token_id = web_hook_token.token_id
                token_fav_dict[token_id] = []
                for favorite in favorite_list:
                    fav_dict = row2dict(favorite, Favorites)
                    fav_dict['token_id'] = token_id
                    fav_dict.pop('user_id', None)
                    token_fav_dict[token_id].append(fav_dict)

            return token_fav_dict
        finally:
            SessionManager.Session.remove()

    def on_success(token_fav_dict):
        for token in token_fav_dict:
            user_favorite_event = UserFavoriteEvent(token=token,
                                                    favorites=token_fav_dict[token])
            dispatcher.new_event(user_favorite_event)

    def on_fail(error):
        logger.error(error, exc_info=True)

    d = threads.deferToThread(query_user_favorite)
    d.addCallback(on_success)
    d.addErrback(on_fail)


@rpc_export
def episode_downloaded(episode_id):

    def query_episode():
        session = SessionManager.Session()
        try:
            (episode, bangumi) = session.query(Episode, Bangumi). \
                join(Bangumi). \
                options(joinedload(Bangumi.cover_image)). \
                options(joinedload(Episode.thumbnail_image)). \
                filter(Episode.delete_mark == None). \
                filter(Episode.id == episode_id).\
                one()
            episode_dict = row2dict(episode, Episode)
            episode_dict['bangumi'] = row2dict(bangumi, Bangumi)
            utils.process_bangumi_dict(bangumi, episode_dict['bangumi'])
            utils.process_episode_dict(episode, episode_dict)
            return episode_dict
        finally:
            SessionManager.Session.remove()

    def on_success(episode):
        episode_event = EpisodeEvent(episode=episode)
        dispatcher.new_event(episode_event)

    def on_fail(error):
        logger.error(error)

    d = threads.deferToThread(query_episode)
    d.addCallback(on_success)
    d.addErrback(on_fail)


@rpc_export
def initialize_web_hook(web_hook_id, web_hook_url, shared_secret):
    """
    when a web hook receive this event, it should invoke the revive API with empty token list
     to update its status to alive.
    :param web_hook_id:
    :param web_hook_url:
    :param shared_secret:
    :return:
    """
    event = InitialEvent(web_hook_id=web_hook_id,
                         url=web_hook_url,
                         shared_secret=shared_secret)

    dispatcher.new_event(event)


@rpc_export
def token_add(web_hook_id, token_id, user_id, email=None):
    """
    When user add a token of web hook
    :param web_hook_id:
    :param token_id:
    :param user_id:
    :param email:
    :return:
    """
    def query_user_favorite():
        session = SessionManager.Session()
        try:
            favorite_list = session.query(Favorites). \
                filter(Favorites.user_id == user_id). \
                all()

            fav_dict_list = []

            for favorite in favorite_list:
                fav_dict = row2dict(favorite, Favorites)
                fav_dict['token_id'] = token_id
                fav_dict.pop('user_id', None)
                fav_dict_list.append(fav_dict)

            return fav_dict_list
        finally:
            SessionManager.Session.remove()

    def on_success(fav_dict_list):
        token_add_event = TokenAddedEvent(web_hook_id=web_hook_id,
                                          favorites=fav_dict_list,
                                          email=email,
                                          token_id=token_id)
        dispatcher.new_event(token_add_event)

    def on_fail(error):
        logger.error(error)

    d = threads.deferToThread(query_user_favorite)
    d.addCallback(on_success)
    d.addErrback(on_fail)


@rpc_export
def token_remove(web_hook_id, token_id):
    token_remove_event = TokenRemovedEvent(web_hook_id=web_hook_id,
                                           token_id=token_id)
    dispatcher.new_event(token_remove_event)


@rpc_export
def email_changed(email, user_id):
    """
    When a user changed its email or registered, this is only triggered after the email is confirmed.
    :param email:
    :param user_id:
    :return:
    """
    def query_token():
        session = SessionManager.Session()
        try:
            token_list = session.query(WebHookToken).\
                options(joinedload(WebHookToken.web_hook)).\
                filter(WebHookToken.user_id == user_id).\
                all()
            token_dict_list = []
            for token in token_list:
                if token.web_hook.status == WebHook.STATUS_IS_DEAD:
                    continue
                if not token.web_hook.has_permission(WebHook.PERMISSION_EMAIL):
                    continue
                token_dict = row2dict(token, WebHookToken)
                token_dict['web_hook'] = row2dict(token.web_hook, WebHook)
                token_dict_list.append(token_dict)
            return token_dict_list
        finally:
            SessionManager.Session.remove()

    def on_success(token_dict_list):
        for token_dict in token_dict_list:
            email_changed_event = UserEmailChangeEvent(token_id=token_dict['token_id'],
                                                       email=email,
                                                       web_hook_id=token_dict['web_hook']['id'],
                                                       web_hook_url=token_dict['web_hook']['url'],
                                                       shared_secret=token_dict['web_hook']['shared_secret'])
            dispatcher.new_event(email_changed_event)

    def on_fail(error):
        logger.error(error)

    d = threads.deferToThread(query_token)
    d.addCallback(on_success)
    d.addErrback(on_fail)


@rpc_export
def delete_deluge_torrent(torrent_id):
    # from utils.DownloadManager import download_manager
    #
    # def on_success(info):
    #     logger.debug(info)
    #     logger.info('{0} deleted'.format(torrent_id,))
    #
    # def on_fail(err):
    #     logger.error('fail to delete torrent of {0}')
    #     logger.error(err, exc_info=True)
    # d = download_manager.remove_torrents((torrent_id,), True)
    # d.addCallback(on_success)
    # d.addErrback(on_fail)
    pass


@rpc_export
def download_complete(video_id, bangumi_id, file_path):

    from utils.DownloadManager import download_manager
    # idx = file_path.find(bangumi_id)
    # file_path = file_path[idx + len(bangumi_id):]
    file_path = urllib.unquote(str(file_path)).decode('utf-8')
    logger.info('download complete ' + video_id + " file: " + file_path)

    def on_success(result):
        logger.info('post process of video file ' + video_id + ' completed, bangumi_id: ' + bangumi_id)

    def on_fail(err):
        logger.error(err)

    d = download_manager.on_download_completed(video_id, file_path)
    d.addCallback(on_success)
    d.addErrback(on_fail)
