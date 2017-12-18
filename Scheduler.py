import logging
import os
import errno
from utils.sentry import sentry_wrapper

from taskrunner.DownloadStatusScanner import download_status_scanner

FORMAT = '%(asctime)-15s %(module)s:%(lineno)d %(message)s'

logging.basicConfig(format=FORMAT, datefmt='%Y/%m/%d %H:%M:%S')

logger = logging.getLogger()

isDebug = os.getenv('DEBUG', False)

if isDebug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


import platform
if platform.system() == 'Linux':
    from twisted.internet import epollreactor
    epollreactor.install()
else:
    from twisted.internet import selectreactor
    selectreactor.install()

from twisted.internet import reactor, threads


from yaml import load
from utils.VideoManager import video_manager
from twisted.internet.task import LoopingCall, deferLater
from utils.DownloadManager import download_manager

from taskrunner.InfoScanner import info_scanner
from taskrunner.FeedScanner import FeedScanner
from taskrunner.DmhyScanner import DmhyScanner
from taskrunner.BangumiMoeScanner import BangumiMoeScanner
from taskrunner.AcgripScanner import AcgripScanner
from taskrunner.LibyksoScanner import LibyksoScanner
from taskrunner.DeleteScanner import DeleteScanner
from rpc.rpc_interface import setup_server
from web_hook.keep_alive_checker import keep_alive_checker


class Scheduler:

    def __init__(self):
        fr = open('./config/config.yml', 'r')
        config = load(fr)
        self.interval = int(config['task']['interval']) * 60
        self.base_path = config['download']['location']
        self.feedparser = config['feedparser']
        self.delete_delay = {'bangumi': 10, 'episode': 1}
        if config['task'].get('delete_delay') is None:
            logger.warn('delete delay section is not set, please update your config file!')
        else:
            self.delete_delay = config['task']['delete_delay']

        try:
            if not os.path.exists(self.base_path):
                os.makedirs(self.base_path)
                logger.info('create base dir %s successfully', self.base_path)
        except OSError as exception:
            if exception.errno == errno.EACCES:
                # permission denied
                raise exception
            else:
                logger.error(exception)

    def start(self):
        self.start_scan_bangumi_moe()
        deferLater(reactor, int(self.interval / 4), self.start_scan_dmhy)
        deferLater(reactor, int(self.interval / 2), self.start_scan_acgrip)
        self.start_scan_libykso() # libyk scanner don't have chance conflict with other scanner, so we can start simultaneously

    def scheduleFail(self, failure):
        logger.error(failure)

    def scheduleDone(self, result):
        logger.error(result)

    def start_scan_dmhy(self):
        logger.debug('start dmhy')
        dmhy_scanner = DmhyScanner(self.base_path, self.interval)
        dmhy_scanner.start()

    def start_scan_acgrip(self):
        logger.debug('start acgrip')
        acgrip_scanner = AcgripScanner(self.base_path, self.interval)
        acgrip_scanner.start()

    def start_scan_libykso(self):
        logger.debug('start libykso')
        libyk_scanner = LibyksoScanner(self.base_path, self.interval)
        libyk_scanner.start()

    def start_scan_bangumi_moe(self):
        logger.debug('start bangumi_moe')
        bangumi_moe_scanner = BangumiMoeScanner(self.base_path, self.interval)
        bangumi_moe_scanner.start()

    def start_scan_feed(self):
        feed_scanner = FeedScanner(self.base_path)
        feed_scanner.start()

    def start_scan_delete(self):
        delete_scanner = DeleteScanner(self.base_path, self.delete_delay)
        delete_scanner.start()


scheduler = Scheduler()

video_manager.set_base_path(scheduler.base_path)

sentry_wrapper.scheduler_sentry()


def on_connected(result):
    logger.info(result)

    # set disconnect callback
    download_manager.set_disconnect_cb(on_disconnect)

    scheduler.start()
    info_scanner.start()
    download_status_scanner.start()
    keep_alive_checker.start()
    scheduler.start_scan_feed()
    scheduler.start_scan_delete()


def on_connect_fail(result):
    logger.error(result)
    sentry_wrapper.client.captureMessage(result)
    reactor.stop()


def on_disconnect():
    sentry_wrapper.client.captureMessage('deluge disconnect unexpectedly')
    reactor.stop()


def stop_tasks():
    logger.info('shutting down...')
    logger.info('stopping InfoScanner...')
    info_scanner.stop()


d = download_manager.connect()
d.addCallback(on_connected)
d.addErrback(on_connect_fail)

setup_server()

reactor.addSystemEventTrigger('before', 'shutdown', stop_tasks)
reactor.run()
