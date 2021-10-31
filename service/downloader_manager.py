import logging

import requests
import yaml

from domain.Bangumi import Bangumi
from domain.Episode import Episode
from domain.VideoFile import VideoFile
from utils.SessionManager import SessionManager
from utils.db import row2dict
from utils.http import json_resp

logger = logging.getLogger(__name__)


class DownloadManagerService:
    def __init__(self):
        fr = open('./config/config.yml', 'r')
        config = yaml.load(fr)
        self.download_manager_url = config['download_manager_url']

    def get_jobs(self, status):
        resp = requests.get(self.download_manager_url + '/download/job', params={
            'status': status
        })

        jobs = resp.json()['data']
        bangumi_id_set = set()

        for job in jobs:
            bangumi_id_set.add(job['bangumiId'])

        bangumi_id_list = list(bangumi_id_set)
        session = SessionManager.Session()
        try:
            bangumi_list = session.query(Bangumi).\
                filter(Bangumi.id.in_(bangumi_id_list)).\
                all()
            for bangumi in bangumi_list:
                bgm = row2dict(bangumi, Bangumi)
                for job in jobs:
                    if job['bangumiId'] == str(bangumi.id):
                        job['bangumi'] = bgm
            return json_resp({
                'data': jobs,
                'total': len(jobs)
            })
        finally:
            SessionManager.Session.remove()

    def enhance_file_mapping(self, file_mapping):
        video_id_list = [entry['videoId'] for entry in file_mapping]
        session = SessionManager.Session()
        try:
            result = session.query(VideoFile, Episode).\
                join(Episode).\
                filter(VideoFile.id.in_(video_id_list)).\
                filter(Episode.id == VideoFile.episode_id).\
                all()
            for entry in file_mapping:
                for video_file, episode in result:
                    entry['episode'] = row2dict(episode, Episode)

            return json_resp({'data': file_mapping, 'total': len(file_mapping)})
        finally:
            SessionManager.Session.remove()


download_manager_service = DownloadManagerService()
