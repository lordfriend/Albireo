from Downloader import Downloader
from yaml import load
from deluge.ui.client import client
from twisted.internet.defer import inlineCallbacks, returnValue
from utils.exceptions import SchedulerError
# Set up the logger to print out errors
from deluge.log import setupLogger, LOG
setupLogger(level='info')


class DelugeDownloader(Downloader):

    def __init__(self, on_download_completed_callback):

        fr = open('./config/config.yml', 'r')
        config = load(fr)
        self.delugeConfig = config['deluge']

        self.__on_download_completed_callback = on_download_completed_callback

    def __on_connect_success(self, result):
        """
        : add event handlers
        """
        LOG.info('Connection was successful')
        client.register_event_handler('TorrentFinishedEvent', self.__on_download_completed)
        return result

    def __on_connect_fail(self, result):
        """
        :throw a exception
        """
        raise Exception()

    def connect_to_daemon(self):
        deferred = client.connect(**self.delugeConfig)

        deferred.addCallback(self.__on_connect_success)
        deferred.addErrback(self.__on_connect_fail)

        return deferred

    def set_on_disconnect_cb(self, cb):
        client.set_disconnect_callback(cb)

    def __on_download_completed(self, torrent_id):
        self.__on_download_completed_callback(torrent_id)


    def __url_type(self, download_url):
        if download_url.startswith('magnet:?'):
            return 'magnet'
        if download_url.endswith('.torrent'):
            return 'torrent'
        if download_url.endswith('.txt'):
            return 'txt'
        return 'unknown'

    @inlineCallbacks
    def download(self, download_url, download_location):
        url_type =self.__url_type(download_url)
        if url_type == 'magnet':
            torrent_id = yield client.core.add_torrent_magnet(download_url, {'download_location': download_location})
        elif url_type == 'torrent':
            torrent_id = yield client.core.add_torrent_url(download_url, {'download_location': download_location})
        else:
            raise SchedulerError('unsupport url format')

        returnValue(torrent_id)

    @inlineCallbacks
    def get_files(self, torrent_id):
        files = yield client.core.get_torrent_status(torrent_id, ['files'])
        returnValue(files['files'])

    @inlineCallbacks
    def remove_torrent(self, torrent_id, remove_data):
        yield client.core.remove_torrent(torrent_id, remove_data)

    @inlineCallbacks
    def get_complete_torrents(self):
        """
        get complete torrents
        :return: a dict which contains all complete torrents (progress = 100), key is torrent_id, value is dict {files: tuple}
        """
        torrent_dict = yield client.core.get_torrents_status({'progress': (100,)}, ['files'])
        returnValue(torrent_dict)

