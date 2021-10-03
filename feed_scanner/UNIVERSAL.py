from feed_scanner.AbstractScanner import AbstractScanner
from utils.constants import VIDEO_FILE_EXT
from utils.exceptions import SchedulerError
import json
import socket
import requests

import logging

logger = logging.getLogger(__name__)


class UNIVERSAL(AbstractScanner):

    def __init__(self, bangumi, episode_list, mode):
        super(self.__class__, self).__init__(bangumi, episode_list)
        self.mode = mode
        self.feed_url = self.universal[mode]
        universal_list = json.loads(self.bangumi.universal)
        for res in universal_list:
            if res['mode'] == mode:
                self.keyword = res['keyword']
                break

    def parse_feed(self):
        logger.debug('start scan %s (%s)', self.bangumi.name, self.bangumi.id)
        eps_no_list = [eps.episode_no for eps in self.episode_list]

        timeout = socket.getdefaulttimeout()
        # set timeout is provided
        if self.timeout is not None:
            timeout = self.timeout

        r = requests.get(self.feed_url, params={'keyword': self.keyword}, timeout=timeout)

        if r.status_code > 399:
            raise SchedulerError('Network Error %d'.format(r.status_code))

        item_array = r.json()

        result_list = []

        for item in item_array:
            eps_list = []
            for media_file in item['files']:
                if media_file['ext'] is None or media_file['ext'].lower() not in VIDEO_FILE_EXT:
                    continue
                eps_no = self.parse_episode_number(media_file['name'])
                if eps_no in eps_no_list:
                    eps_list.append({
                        'eps_no': eps_no,
                        'file_path': media_file['path'],
                        'file_name': media_file['name']
                    })
            if len(eps_list) == 0:
                continue
            for eps in eps_list:
                if self.mode == 'nyaa' or self.mode == 'dmhy':
                    download_uri = item['magnet_uri']
                else:
                    download_uri = item['torrent_url']
                result_list.append((download_uri, eps['eps_no'], eps['file_path'], eps['file_name']))

        logger.debug(result_list)

        return result_list

    @classmethod
    def has_keyword(cls, bangumi):
        return bangumi.universal is not None
