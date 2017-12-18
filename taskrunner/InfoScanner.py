from twisted.internet.defer import inlineCallbacks
from utils.SessionManager import SessionManager
from utils.http import bangumi_request
from domain.Bangumi import Bangumi
from domain.Episode import Episode
from sqlalchemy.sql.expression import or_
from sqlalchemy import exc, func
from twisted.internet import threads
from twisted.internet.task import LoopingCall
from datetime import datetime
import time
import yaml
import logging
import traceback

logger = logging.getLogger(__name__)


class InfoScanner:

    def __init__(self):
        fr = open('./config/config.yml', 'r')
        config = yaml.load(fr)
        if 'info_scanner' in config['task']:
            scan_time = '16:00'
            scan_time_format = '%H:%M'
            if 'scan_time' in config['task']['info_scanner'] and config['task']['info_scanner']['scan_time'] is not None:
                scan_time = config['task']['info_scanner']['scan_time']

            if 'scan_time_format' in config['task']['info_scanner'] and config['task']['info_scanner']['scan_time_format'] is not None:
                scan_time_format = config['task']['info_scanner']['scan_time_format']

            self.scan_time = datetime.strptime(scan_time, scan_time_format)

        self.scanner_running = False
        self.last_scan_date = None
        self.lc = LoopingCall(self.check_time)
        self.terminated = False

    def start(self):
        self.lc.start(60)

    def stop(self):
        self.terminated = True
        if self.lc.running:
            self.lc.stop()

    def check_time(self):
        if self.scanner_running:
            return
        current_time = datetime.utcnow()
        if self.last_scan_date is not None and self.last_scan_date == current_time.date():
            return
        if (not self.scanner_running) and (self.scan_time.hour == current_time.hour):
            self.scanner_running = True
            self.scan_episode()
            self.last_scan_date = current_time.date()
            self.scanner_running = False

    def __check_if_bangumi_finished(self, session, bangumi):
        # if bangumi has no not downloaded episode, we consider it's finished.
        episode_count = session.query(func.count(Episode.id)). \
            filter(Episode.bangumi_id == bangumi.id). \
            filter(Episode.status == Episode.STATUS_NOT_DOWNLOADED). \
            scalar()
        logger.debug('bangumi %s has %d un-downloaded episodes', bangumi.name, episode_count)
        return episode_count == 0

    def __scan_non_finished_bangumi(self):
        """
        scan the bangumi whose status is not finished. and update its status if possible.
        :return:
        """
        session = SessionManager.Session()
        try:
            bangumi_list = session.query(Bangumi). \
                filter(Bangumi.delete_mark == None). \
                filter(Bangumi.status != Bangumi.STATUS_FINISHED). \
                all()
            for bangumi in bangumi_list:
                if bangumi.status == Bangumi.STATUS_PENDING and bangumi.air_date <= datetime.today().date():
                    bangumi.status = Bangumi.STATUS_ON_AIR
                if bangumi.status == Bangumi.STATUS_ON_AIR and self.__check_if_bangumi_finished(session, bangumi):
                    bangumi.status = Bangumi.STATUS_FINISHED
            session.commit()
        except exc.DBAPIError as db_error:
            logger.error(db_error, exc_info=True)
            # if connection is invalid rollback the session
            if db_error.connection_invalidated:
                session.rollback()
        except Exception as error:
            logger.error(error, exc_info=True)
            traceback.print_exc()
        finally:
            SessionManager.Session.remove()

    def get_bgm_info(self, bgm_id):
        bangumi_tv_url_base = 'http://api.bgm.tv/subject/'
        bangumi_tv_url_param = '?responseGroup=large'
        bangumi_tv_url = bangumi_tv_url_base + str(bgm_id) + bangumi_tv_url_param
        try:
            r = bangumi_request.get(bangumi_tv_url)
            if r.status_code < 400:
                return r.status_code, r.json()
            else:
                r.raise_for_status()
        except Exception as error:
            logger.error(error, exc_info=True)
            return -1, None

    def __scan_current_on_air_bangumi(self):
        logger.info('start scan info of episode')
        session = SessionManager.Session()
        try:
            result = session.query(Episode, Bangumi). \
                join(Bangumi). \
                filter(Bangumi.delete_mark == None). \
                filter(Bangumi.status != Bangumi.STATUS_FINISHED)

            bgm_episode_dict = {}

            for episode, bangumi in result:
                # check terminated state to response instantly.
                if self.terminated:
                    return

                if not (bangumi.bgm_id in bgm_episode_dict):
                    # if this is not the first call for get_bgm_info,
                    # a delay should be added to prevent access the bgm api
                    # too frequently
                    if bgm_episode_dict:
                        time.sleep(20)
                    logger.info('try to get info for bangumi of %s' % str(bangumi.bgm_id))
                    (status_code, bangumi_info) = self.get_bgm_info(bangumi.bgm_id)
                    if status_code < 400:
                        bgm_episode_dict[bangumi.bgm_id] = bangumi_info

                if not (bangumi.bgm_id in bgm_episode_dict):
                    continue

                bangumi_info = bgm_episode_dict[bangumi.bgm_id]

                for eps in bangumi_info['eps']:
                    if eps['id'] == episode.bgm_eps_id:
                        if episode.name == '':
                            episode.name = eps['name']
                        if episode.name_cn == '':
                            episode.name_cn = eps['name_cn']
                        if episode.duration == '':
                            episode.duration = eps['duration']
                        # always update airdate because it can be changed.
                        episode.airdate = eps['airdate']
                        break

            session.commit()
            logger.info('scan finished, will scan at next day')
        except exc.DBAPIError as db_error:
            logger.error(db_error, exc_info=True)
            # if connection is invalid rollback the session
            if db_error.connection_invalidated:
                session.rollback()
        except Exception as error:
            logger.error(error, exc_info=True)
            traceback.print_exc()
        finally:
            SessionManager.Session.remove()

    @inlineCallbacks
    def scan_episode(self):
        yield threads.deferToThread(self.__scan_non_finished_bangumi)
        yield threads.deferToThread(self.__scan_current_on_air_bangumi)


info_scanner = InfoScanner()
