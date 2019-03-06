from datetime import datetime

from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func
from sqlalchemy.sql.expression import desc, asc
from utils.SessionManager import SessionManager
from utils.exceptions import ClientError
from utils.http import json_resp, rpc_request
from utils.db import row2dict
from domain.Favorites import Favorites
from domain.WatchProgress import WatchProgress
from domain.Bangumi import Bangumi
from domain.Episode import Episode
from utils.common import utils

import traceback
import logging

logger = logging.getLogger(__name__)


class WatchService:

    def favorite_bangumi(self, bangumi_id, user_id, status):
        session = SessionManager.Session()
        try:
            favorite = session.query(Favorites).\
                filter(Favorites.bangumi_id == bangumi_id).\
                filter(Favorites.user_id == user_id).\
                first()
            if not favorite:
                favorite = Favorites(bangumi_id=bangumi_id, user_id=user_id, status=status)
                session.add(favorite)
            else:
                favorite.status = status
                favorite.update_time = datetime.utcnow()

            session.commit()

            rpc_request.send('user_favorite_update', {'user_id': str(user_id)})

            return json_resp({'message': 'ok', 'status': 0})
        finally:
            SessionManager.Session.remove()

    def delete_bangumi_favorite(self, bangumi_id, user_id):
        session = SessionManager.Session()
        try:
            favorite = session.query(Favorites). \
                filter(Favorites.bangumi_id == bangumi_id). \
                filter(Favorites.user_id == user_id). \
                first()
            if not favorite:
                raise ClientError(ClientError.NOT_FOUND, 404, {bangumi_id: bangumi_id})
            else:
                session.delete(favorite)

            session.commit()

            rpc_request.send('user_favorite_update', {'user_id': str(user_id)})

            return json_resp({'message': 'ok', 'status': 0})
        finally:
            SessionManager.Session.remove()

    def favorite_episode(self, bangumi_id, episode_id, user_id, watch_status):
        session = SessionManager.Session()
        try:
            watch_progress = session.query(WatchProgress).\
                filter(WatchProgress.bangumi_id == bangumi_id).\
                filter(WatchProgress.episode_id == episode_id).\
                filter(WatchProgress.user_id == user_id).\
                first()
            if watch_progress is None:
                watch_progress = WatchProgress(bangumi_id=bangumi_id,
                                               episode_id=episode_id,
                                               user_id=user_id,
                                               watch_status=watch_status)
                session.add(watch_progress)
            else:
                watch_progress.watch_status = watch_status

            session.commit()
            return json_resp({'message': 'ok', 'status': 0})
        finally:
            SessionManager.Session.remove()

    def episode_history(self,
                        bangumi_id,
                        episode_id,
                        user_id,
                        last_watch_position,
                        percentage,
                        is_finished):
        """
        synchronize the episode history,
        if last_watch_time is early than the data in database, the given data will simply be dropped.
        :param bangumi_id:
        :param episode_id:
        :param user_id:
        :param last_watch_position:
        :param percentage:
        :param is_finished:
        :return:
        """
        watch_status = WatchProgress.WATCHED if is_finished else WatchProgress.WATCHING

        session = SessionManager.Session()
        try:
            watch_progress = session.query(WatchProgress).\
                filter(WatchProgress.episode_id == episode_id).\
                filter(WatchProgress.user_id == user_id).\
                first()
            if watch_progress is None:

                watch_progress = WatchProgress(bangumi_id=bangumi_id,
                                               episode_id=episode_id,
                                               user_id=user_id,
                                               watch_status=watch_status,
                                               last_watch_position=last_watch_position,
                                               last_watch_time=datetime.utcnow(),
                                               percentage=percentage)
                session.add(watch_progress)
                session.commit()
            else:
                watch_progress.watch_status = watch_status
                watch_progress.last_watch_time = datetime.utcnow()
                watch_progress.last_watch_position = last_watch_position
                watch_progress.percentage = percentage
                session.commit()

            return json_resp({'message': 'ok', 'status': 0})
        finally:
            SessionManager.Session.remove()

    def synchronize_history(self, user_id, records):
        """
        synchronize client history records with server.
        drop outdated record, drop duplicates on server.
        :param user_id:
        :param records:
        :return:
        """
        episode_id_list = [record['episode_id'] for record in records]
        if len(episode_id_list) == 0:
            return json_resp({'message': 'ok', 'status': 0})
        session = SessionManager.Session()
        try:
            watch_progress_list = session.query(WatchProgress). \
                filter(WatchProgress.user_id == user_id).\
                filter(WatchProgress.episode_id.in_(episode_id_list)).\
                all()

            # remove duplicate records, records can be duplicate when client send records concurrently
            eps_id_dict = {}
            for watch_progress in watch_progress_list:
                episode_id = str(watch_progress.episode_id)
                if episode_id in eps_id_dict:
                    if eps_id_dict[episode_id].last_watch_time < watch_progress.last_watch_time:
                        session.delete(eps_id_dict[episode_id])
                        eps_id_dict[episode_id] = watch_progress
                    else:
                        session.delete(watch_progress)
                else:
                    eps_id_dict[episode_id] = watch_progress

            # synchronize
            for record in records:
                watch_status = WatchProgress.WATCHED if record.get('is_finished') else WatchProgress.WATCHING
                last_watch_time = datetime.utcfromtimestamp(record['last_watch_time'] / 1000)
                record_found = False
                for watch_progress in watch_progress_list:
                    if str(watch_progress.episode_id) == record['episode_id']:
                        record_found = True
                        if watch_progress.last_watch_time <= last_watch_time:
                            watch_progress.watch_status = watch_status
                            watch_progress.last_watch_time = last_watch_time
                            watch_progress.last_watch_position = record['last_watch_position']
                            watch_progress.percentage = record['percentage']
                        break
                if not record_found:
                    watch_progress = WatchProgress(bangumi_id=record['bangumi_id'],
                                                   episode_id=record['episode_id'],
                                                   user_id=user_id,
                                                   watch_status=watch_status,
                                                   last_watch_position=record['last_watch_position'],
                                                   last_watch_time=last_watch_time,
                                                   percentage=record['percentage'])
                    session.add(watch_progress)
            session.commit()
            return json_resp({'message': 'ok', 'status': 0})
        except Exception as error:
            logger.warn(traceback.format_exc(error))
            # always return success even operation failed
            return json_resp({'message': 'ok', 'status': 0})
        finally:
            SessionManager.Session.remove()

    def my_favorites(self, user_id, status=None):
        session = SessionManager.Session()
        try:
            q = session.query(Favorites, Bangumi).\
                join(Bangumi).\
                options(joinedload(Bangumi.cover_image)).\
                filter(Bangumi.delete_mark == None).\
                filter(Favorites.user_id == user_id)

            if status is not None:
                result = q.filter(Favorites.status == status).\
                    order_by(desc(Favorites.update_time)).all()
            else:
                result = q.order_by(desc(Favorites.update_time)).all()

            bangumi_id_list = [bangumi.id for favorite, bangumi in result]
            # print 'bangumi_id_list length: %d' % len(bangumi_id_list)
            if len(bangumi_id_list) == 0:
                return json_resp({'data': [], 'status': 0})

            # query all episode for each favorite that was latest updated.

            latest_eps_update_time = session.query(func.max(Episode.update_time), Episode.bangumi_id).\
                filter(Episode.status == Episode.STATUS_DOWNLOADED).\
                filter(Episode.bangumi_id.in_(bangumi_id_list)).\
                group_by(Episode.bangumi_id).\
                all()

            # subquery for watch_progress
            watch_progress = session.query(WatchProgress.episode_id).\
                filter(WatchProgress.user_id == user_id).\
                filter(WatchProgress.bangumi_id.in_(bangumi_id_list))

            episode_aggregation = session.query(func.count(Episode.id), Episode.bangumi_id).\
                filter(Episode.status == Episode.STATUS_DOWNLOADED).\
                filter(Episode.bangumi_id.in_(bangumi_id_list)).\
                filter(~Episode.id.in_(watch_progress)).\
                group_by(Episode.bangumi_id).\
                all()

            bangumi_dict_list = []

            for fav, bgm in result:
                bangumi_dict = row2dict(bgm, Bangumi)
                bangumi_dict['favorite_status'] = fav.status
                bangumi_dict['favorite_update_time'] = fav.update_time
                bangumi_dict['favorite_check_time'] = fav.check_time
                bangumi_dict['cover'] = utils.generate_cover_link(bangumi)
                utils.process_bangumi_dict(bgm, bangumi_dict)
                for unwatched_count, bangumi_id in episode_aggregation:
                    if bangumi_id == bgm.id:
                        bangumi_dict['unwatched_count'] = unwatched_count
                        break

                for episode_time, bangumi_id in latest_eps_update_time:
                    if bangumi_id == bgm.id:
                        bangumi_dict['eps_update_time'] = episode_time
                bangumi_dict_list.append(bangumi_dict)

            return json_resp({'data': bangumi_dict_list, 'status': 0})

        finally:
            SessionManager.Session.remove()

    def check_favorite(self, bangumi_id, user_id):
        session = SessionManager.Session()
        favorite = session.query(Favorites).\
            filter(Favorites.bangumi_id == bangumi_id).\
            filter(Favorites.user_id == user_id).\
            first()
        if not favorite:
            return json_resp({'data': 0, 'status': 0})
        else:
            favorite.check_time = datetime.utcnow()
            return json_resp({'data': favorite.check_time, 'status': favorite.status})


watch_service = WatchService()
