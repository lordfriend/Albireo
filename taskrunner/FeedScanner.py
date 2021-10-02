from twisted.internet.task import LoopingCall
from twisted.internet import reactor, threads
from twisted.internet.defer import inlineCallbacks, returnValue

from domain.Image import Image
from utils.SessionManager import SessionManager
from utils.DownloadManager import download_manager
from utils.VideoManager import video_manager
from domain.Feed import Feed
from domain.Episode import Episode
from domain.VideoFile import VideoFile
from domain.WatchProgress import WatchProgress
from domain.Favorites import Favorites
from datetime import datetime

import logging

from utils.image import get_dominant_color, get_dimension

logger = logging.getLogger(__name__)

class FeedScanner:
    '''
    This scanner will scan the 'feed' table with special interval. if any record has a field torrent_file_id is null.
    scanner will add this record to download application and get the torrent_file_id
    '''

    def __init__(self, base_path):
        self.interval = 30
        self.base_path = base_path

    def start(self):
        lc = LoopingCall(self.scan_feed)
        lc.start(self.interval)

        # lc2 = LoopingCall(self.scan_downloading)
        # lc2.start(self.interval * 2)

    def __query_video_file(self):
        session = SessionManager.Session()
        try:
            return session.query(VideoFile).\
                filter(VideoFile.download_url != None).\
                filter(VideoFile.status == VideoFile.STATUS_DOWNLOAD_PENDING).\
                all()
        finally:
            SessionManager.Session.remove()

    def __query_downloading_video_file(self):
        session = SessionManager.Session()
        try:
            return session.query(VideoFile).\
                filter(VideoFile.torrent_id != None).\
                filter(VideoFile.status != VideoFile.STATUS_DOWNLOADED).\
                all()
        finally:
            SessionManager.Session.remove()

    def __update_video_file(self, video_file_list, task_id):
        session = SessionManager.Session()
        try:
            for video_file in video_file_list:
                session.add(video_file)
                video_file.task_id = task_id
                video_file.status = VideoFile.STATUS_DOWNLOADING
            session.commit()
        finally:
            SessionManager.Session.remove()

    def __create_thumbnail(self, episode, file_path):
        time = '00:00:01.000'
        video_manager.create_episode_thumbnail(episode, file_path, time)
        thumbnail_path = '{0}/thumbnails/{1}.png'.format(str(episode.bangumi_id), episode.episode_no)
        thumbnail_file_path = '{0}/{1}'.format(self.base_path, thumbnail_path)
        color = get_dominant_color(thumbnail_file_path)
        width, height = get_dimension(thumbnail_file_path)
        episode.thumbnail_image = Image(file_path=thumbnail_path,
                                        dominant_color=color,
                                        width=width,
                                        height=height)
        episode.thumbnail_color = color

    def __update_video_meta(self, video_file):
        meta = video_manager.get_video_meta(u'{0}/{1}/{2}'.format(self.base_path, str(video_file.bangumi_id), video_file.file_path))
        if meta is not None:
            video_file.duration = meta.get('duration')
            video_file.resolution_w = meta.get('width')
            video_file.resolution_h = meta.get('height')

    def __update_info(self, video_file):
        session = SessionManager.Session()
        try:
            episode = session.query(Episode).\
                filter(Episode.id == video_file.episode_id).\
                one()
            episode.status = Episode.STATUS_DOWNLOADED
            episode.update_time = datetime.utcnow()
            self.__create_thumbnail(episode, video_file.file_path)
            self.__update_video_meta(video_file)
            session.add(video_file)
            session.commit()
            video_file_id = str(video_file.id)
            return video_file_id
        except Exception as error:
            logger.error(error, exc_info=True)
        finally:
            SessionManager.Session.remove()

    @inlineCallbacks
    def __add_download(self, video_file_list):
        logger.debug(video_file_list)
        download_url_dict = {}
        for video_file in video_file_list:
            if video_file.download_url not in download_url_dict:
                download_url_dict[video_file.download_url] = []
            download_url_dict[video_file.download_url].append(video_file)

        for download_url, same_torrent_video_file_list in download_url_dict.iteritems():
            first_video_file = same_torrent_video_file_list[0]
            file_mapping = None
            video_id = None
            if len(same_torrent_video_file_list) > 1 or same_torrent_video_file_list[0].file_path is not None:
                file_mapping = [{'filePath': video_file.file_path, 'videoId': str(video_file.id)} for video_file in same_torrent_video_file_list]
            else:
                video_id = str(first_video_file.id)
            # bangumi_path = self.base_path + '/' + str(first_video_file.bangumi_id)
            try:
                task_id = yield download_manager.download(download_url, str(first_video_file.bangumi_id), video_id, file_mapping)
                yield threads.deferToThread(self.__update_video_file, same_torrent_video_file_list, task_id)
            except Exception as error:
                logger.error(error, exc_info=True)
                logger.error('episode %s download failed', str(first_video_file.episode_id))

    # @inlineCallbacks
    # def __fix_video_file(self, video_file_list):
    #     torrent_dict = yield download_manager.get_complete_torrents()
    #     fixed_video_file_ids = []
    #     for video_file in video_file_list:
    #         if video_file.torrent_id in torrent_dict:
    #             # this video_file status is wrong, update it
    #             file_list = torrent_dict[video_file.torrent_id]['files']
    #             if video_file.file_path is None and video_file.file_name is None:
    #                 if len(file_list) == 1:
    #                     # only one file
    #                     file_path = file_list[0]['path']
    #                 elif len(file_list) > 1:
    #                     max_size = file_list[0]['size']
    #                     main_file = file_list[0]
    #                     for file in file_list:
    #                         if not file['path'].endswith('.mp4'):
    #                             continue
    #                         if file['size'] > max_size:
    #                             main_file = file
    #
    #                     file_path = main_file['path']
    #                 else:
    #                     logger.warn('no file found in %s', video_file.torrent_id)
    #                     continue
    #                 video_file.file_path = file_path
    #                 video_file.status = VideoFile.STATUS_DOWNLOADED
    #                 video_file_id = yield threads.deferToThread(self.__update_info, video_file)
    #                 fixed_video_file_ids.append(video_file_id)
    #             else:
    #                 file_path_list = [file['path'] for file in file_list]
    #                 for file_path in file_path_list:
    #                     if video_file.file_name is not None and video_file.file_path is None and file_path.endswith(video_file.file_name):
    #                         video_file.file_path = file_path
    #                         video_file.status = VideoFile.STATUS_DOWNLOADED
    #                         video_file_id = yield threads.deferToThread(self.__update_info, video_file)
    #                         fixed_video_file_ids.append(video_file_id)
    #                         break
    #                     elif video_file.file_path is not None and file_path == video_file.file_path:
    #                         video_file.status = VideoFile.STATUS_DOWNLOADED
    #                         video_file_id = yield threads.deferToThread(self.__update_info, video_file)
    #                         fixed_video_file_ids.append(video_file_id)
    #                         break
    #     if len(fixed_video_file_ids) > 0:
    #         logger.info('fixed video_files: %s', str(fixed_video_file_ids))


    def __on_query_error(self, err):
        logger.error(err, exc_info=True)

    def scan_feed(self):
        logger.info('scan feed')
        d = threads.deferToThread(self.__query_video_file)
        d.addCallback(self.__add_download)
        d.addErrback(self.__on_query_error)

    # def scan_downloading(self):
    #     logger.info('scan downloading')
    #     '''
    #     scan downloading status video_file, find error status video_file and auto correct it.
    #     :return:
    #     '''
    #     d = threads.deferToThread(self.__query_downloading_video_file)
    #     d.addCallback(self.__fix_video_file)
    #     d.addErrback(self.__on_query_error)
