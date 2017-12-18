from utils.SessionManager import SessionManager
from domain.Bangumi import Bangumi
from domain.Episode import Episode
from domain.WatchProgress import WatchProgress
from domain.Favorites import Favorites
from domain.Feed import Feed
from domain.VideoFile import VideoFile
from datetime import datetime
from sqlalchemy.sql import func, or_
import logging
import random
from twisted.internet import threads
from twisted.internet.task import LoopingCall
from twisted.internet.defer import inlineCallbacks, returnValue

logger = logging.getLogger(__name__)


class BangumiScanner(object):

    def __init__(self, base_path, interval):
        self.base_path = base_path
        self.interval = interval

    def __find_episode_by_number(self, episode_list, eps_no):
        for episode in episode_list:
            if episode.episode_no == eps_no:
                return episode
        return None

    def __drop_duplicate(self, url_eps_id_list):
        eps_id_dict = {}
        no_dupli_list = []
        for (download_url, episode, file_path, file_name) in url_eps_id_list:
            if str(episode.id) not in eps_id_dict:
                no_dupli_list.append((download_url, episode, file_path, file_name))
                eps_id_dict[str(episode.id)] = True

        return no_dupli_list

    def save_video_file(self, video_file, episode, session):
        try:
            session.add(video_file)
            session.add(episode)
            session.commit()
        except:
            session.rollback()


    def download_episodes(self, url_eps_list, bangumi_id):
        no_dupli_list = self.__drop_duplicate(url_eps_list)
        session = SessionManager.Session()
        try:
            for (download_url, episode, file_path, file_name) in no_dupli_list:
                video_file = VideoFile(episode_id=episode.id,
                                       bangumi_id=bangumi_id,
                                       download_url=download_url,
                                       file_name=file_name,
                                       file_path=file_path)
                episode.status = Episode.STATUS_DOWNLOADING
                self.save_video_file(video_file, episode, session)
                logger.info('%s save to video_file', str(episode.id))
        except Exception as error:
            logger.error(error, exc_info=True)
        finally:
            SessionManager.Session.remove()

    def check_bangumi_status(self, bangumi):
        return bangumi.status == Bangumi.STATUS_FINISHED

    # def update_bangumi_on_air(self, bangumi):
    #     if bangumi.air_date <= datetime.today().date():
    #         bangumi.status = Bangumi.STATUS_ON_AIR

    def update_bangumi_status(self, bangumi):
        session = SessionManager.Session
        try:
            # if bangumi has no not downloaded episode, we consider it's finished.
            episode_count = session.query(func.count(Episode.id)). \
                filter(Episode.bangumi_id == bangumi.id). \
                filter(Episode.status == Episode.STATUS_NOT_DOWNLOADED). \
                scalar()
            logger.debug('bangumi %s has %d un-downloaded episodes', bangumi.name, episode_count)
            if (bangumi.status == Bangumi.STATUS_ON_AIR) and (episode_count == 0):
                session.add(bangumi)
                bangumi.status = Bangumi.STATUS_FINISHED
                session.commit()
        except Exception as error:
            logger.error(error, exc_info=True)
        finally:
            SessionManager.Session.remove()

    def query_bangumi_list(self):
        """
        Subclass should override this method
        :return: a bangumi list
        """
        return []

    def query_episode_list(self, bangumi_id):
        session = SessionManager.Session()
        try:
            return session.query(Episode). \
                filter(Episode.bangumi_id == bangumi_id). \
                filter(Episode.status == Episode.STATUS_NOT_DOWNLOADED). \
                all()
        except Exception as error:
            logger.error(error, exc_info=True)
            return []
        finally:
            SessionManager.Session.remove()

    def scan_feed(self,bangumi, episode_list):
        """
        subclass should override this method
        :param bangumi,
        :param episode_list
        :return: list of tuples (download_url, episode_no)
        """
        returnValue([])

    @inlineCallbacks
    def scan_bangumi(self):
        """
        dispatch the feed crawling job, this is a synchronized method running on individual thread
        :return:
        """
        logger.info('scan bangumi %s', self.__class__.__name__)
        bangumi_list = yield threads.deferToThread(self.query_bangumi_list)
        index_list = range(len(bangumi_list))
        random.shuffle(index_list)
        for index in index_list:
            bangumi = bangumi_list[index]
            if not self.check_bangumi_status(bangumi):
                episode_list = yield threads.deferToThread(self.query_episode_list, bangumi.id)
                # result is an array of tuple (item, eps_no)
                scan_result = yield threads.deferToThread(self.scan_feed, bangumi, episode_list)
                if scan_result is None:
                    continue
                url_eps_list = [
                    (download_url, self.__find_episode_by_number(episode_list, eps_no), file_path, file_name)
                    for (download_url, eps_no, file_path, file_name) in scan_result
                ]
                # this method may raise exception
                yield threads.deferToThread(self.download_episodes, url_eps_list, bangumi.id)
                yield threads.deferToThread(self.update_bangumi_status, bangumi)

    def start(self):
        lp = LoopingCall(self.scan_bangumi)
        lp.start(self.interval)
