import json

import requests
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import threads
from domain.Episode import Episode
from domain.VideoFile import VideoFile
from domain.Image import Image
from utils.SessionManager import SessionManager
from utils.VideoManager import video_manager
from datetime import datetime
from sqlalchemy import exc
from utils.image import get_dominant_color, get_dimension
from rpc.rpc_interface import episode_downloaded
from uuid import uuid4
import logging
import yaml

logger = logging.getLogger(__name__)


class DownloadManager:

    def __init__(self):
        fr = open('./config/config.yml', 'r')
        config = yaml.load(fr)
        self.base_path = config['download']['location']
        self.download_manager_url = config['download_manager_url']

    @inlineCallbacks
    def on_download_completed(self, video_id, file_path):
        logger.info('Download complete: %s ', video_id)

        def create_thumbnail(episode):
            time = '00:00:01.000'
            video_manager.create_episode_thumbnail(episode, file_path, time)
            try:
                thumbnail_path = '{0}/thumbnails/{1}.png'.format(str(episode.bangumi_id), episode.episode_no)
                thumbnail_file_path = '{0}/{1}'.format(self.base_path, thumbnail_path)
                color = get_dominant_color(thumbnail_file_path)
                width, height = get_dimension(thumbnail_file_path)
                episode.thumbnail_image = Image(file_path=thumbnail_path,
                                                dominant_color=color,
                                                width=width,
                                                height=height)
                episode.thumbnail_color = color
            except Exception as error:
                logger.error(error, exc_info=True)

        def update_video_meta(video_file):
            meta = video_manager.get_video_meta(u'{0}/{1}/{2}'.format(self.base_path, str(video_file.bangumi_id), video_file.file_path))
            if meta is not None:
                video_file.duration = meta.get('duration')
                video_file.resolution_w = meta.get('width')
                video_file.resolution_h = meta.get('height')

        def update_video_files():
            session = SessionManager.Session()
            try:
                (video_file, episode) = session.query(VideoFile, Episode).\
                    join(Episode).\
                    filter(VideoFile.id == video_id).\
                    filter(Episode.id == VideoFile.episode_id).\
                    one()
                video_file.file_path = file_path
                video_file.status = VideoFile.STATUS_DOWNLOADED
                episode.update_time = datetime.utcnow()
                episode.status = Episode.STATUS_DOWNLOADED
                create_thumbnail(episode)
                update_video_meta(video_file)
                episode_id = str(episode.id)

                session.commit()
                return episode_id
            except exc.DBAPIError as db_error:
                if db_error.connection_invalidated:
                    session.rollback()
            finally:
                SessionManager.Session.remove()

        eps_id = yield threads.deferToThread(update_video_files)
        # send an event to web_hook
        episode_downloaded(episode_id=eps_id)

    @inlineCallbacks
    def download(self, download_url, bangumi_id, video_id, file_mapping=None):
        task_id = str(uuid4())

        def rpc_call():
            rpc_url = self.download_manager_url + '/rpc/download'
            return requests.post(rpc_url, json={
                'id': task_id,
                'version': '1.0',
                'bangumiId': bangumi_id,
                'torrentUrl': download_url,
                'fileMapping': file_mapping,
                'videoId': video_id
            })

        resp = yield threads.deferToThread(rpc_call)
        logger.info(resp)
        returnValue(task_id)

    def remove_torrents(self, torrent_id_list, remove_data):
        # result_list = []
        # for torrent_id in torrent_id_list:
        #     result = yield self.downloader.remove_torrent(torrent_id, remove_data)
        #     result_list.append(result)
        # returnValue(result_list)
        pass

    # @inlineCallbacks
    # def get_complete_torrents(self):
    #     torrent_dict = yield self.downloader.get_complete_torrents()
    #     returnValue(torrent_dict)


download_manager = DownloadManager()
