import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from twisted.internet import threads, reactor
from twisted.internet.task import LoopingCall

from domain.Bangumi import Bangumi
from domain.Episode import Episode
from domain.Favorites import Favorites
from domain.Image import Image
from domain.Task import Task
from domain.VideoFile import VideoFile
from domain.WatchProgress import WatchProgress
from utils.DownloadManager import download_manager
from utils.SessionManager import SessionManager
from utils.db import row2dict
from utils.http import DateTimeEncoder

logger = logging.getLogger(__name__)


class DeleteScanner:

    def __init__(self, base_path, delete_delay):
        self.interval = 60
        self.base_path = base_path
        self.bangumi_delete_delay = delete_delay['bangumi']

    def start(self):
        lc = LoopingCall(self.scan_delete)
        lc.start(self.interval)

    def __unshift_task_step(self, task_content, task, session):
        task_content['task_step'].pop(0)
        task.content = json.dumps(task_content)
        session.commit()

    def delete_bangumi(self, bangumi):
        session = SessionManager.Session()
        try:
            # add related information to database
            task_content = {'bangumi_id': str(bangumi.id)}
            episode_list = session.query(Episode).filter(Episode.bangumi_id == bangumi.id).all()
            episode_id_list = [episode.id for episode in episode_list]
            video_file_list = session.query(VideoFile).filter(VideoFile.bangumi_id == bangumi.id).all()
            watch_progress_list = session.query(WatchProgress).filter(WatchProgress.episode_id.in_(episode_id_list)).all()
            favorite_list = session.query(Favorites).filter(Favorites.bangumi_id == bangumi.id).all()

            task_content['torrent_id_list'] = list(set([video_file.torrent_id for video_file in video_file_list]))
            task_content['task_step'] = ['db', 'torrent', 'file_system']

            task = Task(type=Task.TYPE_BANGUMI_DELETE, content=json.dumps(task_content, cls=DateTimeEncoder), status=Task.STATUS_IN_PROGRESS)
            session.add(task)
            session.commit()


            # video file
            for video_file in video_file_list:
                session.delete(video_file)

            # remove watch-progress
            for watch_progress in watch_progress_list:
                session.delete(watch_progress)

            # remove episode
            for episode in episode_list:
                session.delete(episode)

            # remove favorites
            for favorite in favorite_list:
                session.delete(favorite)

            # remove image
            if bangumi.cover_image_id is not None:
                image = session.query(Image).filter(Image.id == bangumi.cover_image_id).one()
                session.delete(image)

            # remove bangumi
            session.delete(bangumi)

            self.__unshift_task_step(task_content, task, session)

            if len(task_content['torrent_id_list']) > 0:
                # remove torrent from deluge
                try:
                    threads.blockingCallFromThread(reactor, download_manager.remove_torrents, task_content['torrent_id_list'], False)
                except Exception as error:
                    logger.warn(error)
            self.__unshift_task_step(task_content, task, session)

            # remove files of bangumi
            bangumi_folder_path = '{0}/{1}'.format(self.base_path, str(bangumi.id))
            shutil.rmtree(bangumi_folder_path, ignore_errors=True)
            task_content['task_step'].pop(0)
            task.content = json.dumps(task_content)
            task.status = Task.STATUS_COMPLETE
            session.commit()

            return str(task.id)
        finally:
            SessionManager.Session.remove()

    def __dispatch_delete_bangumi(self, bangumi_list):
        for bangumi in bangumi_list:
            d = threads.deferToThread(self.delete_bangumi, bangumi)
            d.addCallback(self.__on_delete_callback)
            d.addErrback(self.__on_delete_errCallback)

    def __on_delete_callback(self, id):
        logger.debug('delete task id#{0} added'.format(id,))

    def __on_delete_errCallback(self, err):
        logger.error(err, exc_info=True)

    def __query_error(self, err):
        logger.error(err, exc_info=True)

    def scan_bangumi(self):
        session = SessionManager.Session()
        try:
            task_list = session.query(Task).\
                filter(Task.status != Task.STATUS_COMPLETE).\
                filter(Task.type == Task.TYPE_BANGUMI_DELETE).\
                all()
            bangumi_id_in_task = []
            for task in task_list:
                content_dict = json.loads(task.content)
                bangumi_id_in_task.append(content_dict['bangumi_id'])

            latest_delete_time = datetime.now() - timedelta(minutes=self.bangumi_delete_delay)

            query = session.query(Bangumi)

            if len(bangumi_id_in_task) > 0:
                query = query.filter(Bangumi.id.notin_(bangumi_id_in_task))

            bangumi_list = query.\
                filter(Bangumi.delete_mark != None).\
                filter(Bangumi.delete_mark <= latest_delete_time).\
                all()

            return bangumi_list
        finally:
            SessionManager.Session.remove()

    def scan_delete(self):
        logger.info('scan delete')
        bgm_d = threads.deferToThread(self.scan_bangumi)
        bgm_d.addCallback(self.__dispatch_delete_bangumi)
        bgm_d.addErrback(self.__query_error)
