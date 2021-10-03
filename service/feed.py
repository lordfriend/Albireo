# -*- coding: utf-8 -*-

import yaml
import feedparser
import urllib2
import urllib
import socket
import re
import logging
import requests

from utils.exceptions import ClientError
from utils.http import json_resp, bangumi_moe_request
from utils.constants import episode_regex_tuple, VIDEO_FILE_EXT

logger = logging.getLogger(__name__)


class FeedService(object):

    def __init__(self):
        fr = open('./config/config.yml', 'r')
        config = yaml.load(fr)
        self.feedparser_config = config['feedparser']
        self.universal = config.get('universal')

        if 'timeout' in self.feedparser_config:
            self.timeout = int(self.feedparser_config['timeout'])
        else:
            self.timeout = None

    def _get_proxy(self, site_name):
        """
        get the proxy config from config and given url,
        if url specific config is not found using the default config.
        if config is an string, treat it as proxy url, use it for all three schemes
        if config is an dict, make sure it has all scheme set and use it directly
        :param site_name:
        :return: an dict of config
        """
        if 'proxy' in self.feedparser_config:
            proxy_config = self.feedparser_config['proxy']
            # find config by name, if not found, use default, if default is not set, return None
            if site_name in proxy_config:
                proxy_for_name = proxy_config[site_name]
            elif 'default' in proxy_config:
                proxy_for_name = proxy_config['default']
            else:
                return None

            if type(proxy_for_name) is str:
                return {'http': proxy_for_name, 'https': proxy_for_name, 'ftp': proxy_for_name}
            elif type(proxy_for_name) is dict:
                return proxy_for_name
            else:
                return None

    def parse_episode_number(self, eps_title):
        """
        parse the episode number from episode title, it use a list of regular expressions. the position in the list
        is the priority of the regular expression.
        :param eps_title: the title of episode.
        :return: episode number if matched, otherwise, -1
        """
        try:
            for regex in episode_regex_tuple:
                search_result = re.search(regex, eps_title, re.U | re.I)
                if search_result is not None:
                    return int(search_result.group(1))

            return -1
        except Exception:
            return -1

    def parse_feed(self, site_name, feed_url):

        proxy = self._get_proxy(site_name)

        default_timeout = socket.getdefaulttimeout()

        # set timeout is provided
        if self.timeout is not None:
            socket.setdefaulttimeout(self.timeout)

        # use handlers
        if proxy is not None:
            proxy_handler = urllib2.ProxyHandler(proxy)
            feed_dict = feedparser.parse(feed_url, handlers=[proxy_handler])
        else:
            feed_dict = feedparser.parse(feed_url)

        # restore the default timeout
        if self.timeout is not None:
            socket.setdefaulttimeout(default_timeout)

        if feed_dict.bozo != 0:
            logger.warn(feed_dict.bozo_exception)
            raise ClientError(feed_dict.bozo_exception.getMessage())
        return feed_dict

    def parse_dmhy(self, keywords):
        keywords_encoded = urllib.quote_plus(keywords.replace(u'+', u' ').encode('utf-8'))
        feed_url = 'https://share.dmhy.org/topics/rss/rss.xml?keyword=%s' % (keywords_encoded,)
        feed_dict = self.parse_feed('dmhy', feed_url)
        title_list = []
        for item in feed_dict.entries:
            item_title = item['title']
            eps_no = self.parse_episode_number(item_title)
            title_list.append({'title': item_title, 'eps_no': eps_no})

        return json_resp({'data': title_list, 'status': 0})

    def parse_acg_rip(self, keywords):
        keywords_encoded = urllib.quote_plus(keywords.replace(u'+', u' ').encode('utf-8'))
        feed_url = 'https://acg.rip/.xml?term=%s' % (keywords_encoded,)
        feed_dict = self.parse_feed('acg.rip', feed_url)
        title_list = []
        for item in feed_dict.entries:
            item_title = item['title']
            eps_no = self.parse_episode_number(item_title)
            title_list.append({'title': item_title, 'eps_no': eps_no})

        return json_resp({'data': title_list, 'status': 0})

    def parse_libyk_so(self, t, q):
        t_encoded = urllib.quote_plus(t.replace(u'+', u' ').encode('utf-8'))
        q_encoded = urllib.quote_plus(q.replace(u'+', u' ').encode('utf-8'))
        feed_url = 'https://utils.libyk.com/torrent/rss?m=magnet&t={0}&q={1}'.format(t_encoded, q_encoded)
        feed_dict = self.parse_feed('libyk_so', feed_url)
        title_list = []
        for item in feed_dict.entries:
            item_title = item['title']
            eps_no = self.parse_episode_number(item_title)
            title_list.append({'title': item_title, 'eps_no': eps_no})

        return json_resp({'data': title_list, 'status': 0})

    def bangumi_moe_proxy(self, url, method, payload):
        result = {}

        r = bangumi_moe_request.send(url, method, payload)
        if r.status_code > 399:
            r.raise_for_status()

        try:
            return r.text
        except Exception as error:
            logger.warn(error)
            result['message'] = 'fail to query bangumi'
            return json_resp(result, 500)

    def parse_bangumi_moe(self, tag_ids):
        result = {}

        r = bangumi_moe_request.post('https://bangumi.moe/api/torrent/search', tag_ids)
        if r.status_code > 399:
            r.raise_for_status()

        try:
            search_result = r.json()
        except Exception as error:
            logger.warn(error)
            result['message'] = 'fail to query bangumi'
            return json_resp(result, 500)

        for torrent in search_result['torrents']:
            torrent['eps_no_list'] = []
            for content in torrent['content']:
                file_name = content[0]
                if not file_name.endswith(('.mp4',)):
                    continue
                eps_no = self.parse_episode_number(file_name)
                torrent['eps_no_list'].append(eps_no)

        return json_resp(search_result)

    def parse_nyaa(self, qs):
        feed_url = 'https://nyaa.si/?page=rss&{0}'.format(qs,)
        feed_dict = self.parse_feed('nyaa', feed_url)
        title_list = []
        for item in feed_dict.entries:
            item_title = item['title']
            eps_no = self.parse_episode_number(item_title)
            title_list.append({'title': item_title, 'eps_no': eps_no})

        return json_resp({'data': title_list, 'status': 0})

    def parse_universal(self, mode, keyword):
        result = {}
        r = requests.get(self.universal[mode], params={'keyword': keyword})
        if r.status_code > 399:
            r.raise_for_status()

        try:
            search_result = r.json()
        except Exception as error:
            logger.warn(error)
            result['message'] = 'fail to query universal {0}'.format(mode)
            return json_resp(result, 500)
        for item in search_result:
            media_files = item['files']
            item['eps_no_list'] = []
            for media_file in media_files:
                if media_file['ext'] not in VIDEO_FILE_EXT:
                    continue
                eps_no = self.parse_episode_number(media_file['name'])
                item['eps_no_list'].append({'eps_no': eps_no, 'format': media_file['ext'][1:]})
        return json_resp({'data': search_result, 'status': 0})

    def get_universal_meta(self):
        if self.universal is None:
            return json_resp({'data': [], 'status': 0})
        else:
            return json_resp({'data': list(self.universal.keys()), 'status': 0})


feed_service = FeedService()
