import logging
from twisted.internet import threads
from twisted.internet.task import LoopingCall

import yaml
import os
from datetime import datetime, timedelta

from sender import Mail, Message
from sqlalchemy import exc
from sqlalchemy.orm import joinedload

from domain.Bangumi import Bangumi
from domain.Episode import Episode
from domain.User import User
from utils.SessionManager import SessionManager
from jinja2 import Template, Environment, FileSystemLoader

logger = logging.getLogger(__name__)

isDebug = os.getenv('DEBUG', False)

if isDebug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


# noinspection PyComparisonWithNone
class DownloadStatusScanner:

    def __init__(self):
        fr = open('./config/config.yml', 'r')
        config = yaml.load(fr)
        if 'download_status_scanner' in config['task']:
            scan_time = '05:00'
            scan_time_format = '%H:%M'
            if 'scan_time' in config['task']['download_status_scanner'] and\
                    config['task']['download_status_scanner']['scan_time'] is not None:
                scan_time = config['task']['download_status_scanner']['scan_time']

            if 'scan_time_format' in config['task']['download_status_scanner'] and\
                    config['task']['download_status_scanner']['scan_time_format'] is not None:
                scan_time_format = config['task']['download_status_scanner']['scan_time_format']
            self.scan_time = datetime.strptime(scan_time, scan_time_format)
        self.scanner_running = False
        self.last_scan_date = None
        # mail instance
        self.mail_config = config['mail']
        self.mail = Mail(self.mail_config['mail_server'],
                         port=self.mail_config['mail_port'],
                         username=self.mail_config['mail_username'],
                         password=self.mail_config['mail_password'],
                         use_tls=self.mail_config['mail_use_tls'],
                         use_ssl=self.mail_config['mail_use_ssl'])
        # root path of site
        self.root_path = '{0}://{1}'.format(config['site']['protocol'], config['site']['host'])

        # mail template
        # tfr = open('./templates/download-status-alert.html', 'r')
        env = Environment(
            loader=FileSystemLoader('./templates')
        )
        self.mail_template = env.get_template('download-status-alert.html')

    def start(self):
        lc = LoopingCall(self.check_time)
        lc.start(60)

    def check_time(self):
        if self.scanner_running:
            return
        current_time = datetime.utcnow()
        if self.last_scan_date is not None and self.last_scan_date == current_time.date():
            return
        if (not self.scanner_running) and (self.scan_time.hour == current_time.hour):
            self.scanner_running = True
            self.scan_download_status()
            self.last_scan_date = current_time.date()
            self.scanner_running = False

    def scan_download_status(self):
        threads.deferToThread(self.__scan_download_status_in_thread)

    def __scan_download_status_in_thread(self):
        session = SessionManager.Session()
        try:
            current_time = datetime.utcnow()
            result = session.query(Episode).\
                options(joinedload(Episode.bangumi).joinedload(Bangumi.maintained_by)).\
                filter(Episode.airdate != None).\
                filter(Episode.status != Episode.STATUS_DOWNLOADED).\
                filter(Episode.airdate > current_time).\
                filter(Bangumi.status != Bangumi.STATUS_FINISHED).\
                all()

            admin_map = {}

            for (episode, bangumi) in result:
                if episode.airdate - current_time < timedelta(days=bangumi.alert_timeout):
                    continue
                bangumi_id = str(bangumi.id)
                if bangumi.maintained_by is None:
                    if 'sys' not in admin_map:
                        admin_map['sys'] = {}
                    if bangumi_id not in admin_map['sys']:
                        admin_map['sys'][bangumi_id] = {
                            'bangumi': bangumi,
                            'episodes': []
                        }
                    admin_map['sys'][bangumi_id]['episodes'].append(episode)
                else:
                    maintainer_uid = str(bangumi.maintained_by.id)
                    if maintainer_uid not in admin_map:
                        admin_map[maintainer_uid] = {
                            'user': bangumi.maintained_by,
                            'bangumi_map': {}
                        }
                    if bangumi_id not in admin_map[maintainer_uid]:
                        admin_map[maintainer_uid]['bangumi_map'][bangumi_id] = {
                            'bangumi': bangumi,
                            'episodes': []
                        }
                    admin_map[maintainer_uid]['bangumi_map'][bangumi_id].append(episode)

            for uid in admin_map:
                if uid == 'sys':
                    all_admin_list = session.query(User).filter(User.level >= User.LEVEL_ADMIN).all()
                    self.__send_email_to_all(all_admin_list, admin_map['sys'])
                else:
                    self.__send_email_to(admin_map[uid]['user'], admin_map[uid]['bangumi_map'])

        except exc.DBAPIError as db_error:
            logger.error(db_error)
            # if connection is invalid rollback the session
            if db_error.connection_invalidated:
                session.rollback()
        finally:
            SessionManager.Session.remove()

    def __send_email_to(self, user, bangumi_map):
        info = {
            'username': user.name,
            'root_path': self.root_path,
            'sys': False
        }
        bangumi_list = [bangumi_map[bangumi_id] for bangumi_id in bangumi_map]
        msg = Message('Download Status Alert', fromaddr=('Alert System', self.mail_config['mail_default_sender']))
        msg.to = user.email
        msg.body = self.mail_template.render(info=info, bangumi_list=bangumi_list)

    def __send_email_to_all(self, admin_list, bangumi_map):
        for user in admin_list:
            info = {
                'username': user.name,
                'root_path': self.root_path,
                'sys': True
            }
            bangumi_list = [bangumi_map[bangumi_id] for bangumi_id in bangumi_map]
            msg = Message('Download Status Alert', fromaddr=('Alert System', self.mail_config['mail_default_sender']))
            msg.to = user.email
            msg.body = self.mail_template.render(info=info, bangumi_list=bangumi_list)

