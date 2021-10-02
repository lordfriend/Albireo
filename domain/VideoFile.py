from domain.base import Base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from uuid import uuid4

class VideoFile(Base):
    __tablename__ = 'video_file'


    id = Column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4)
    bangumi_id = Column(postgresql.UUID(as_uuid=True), ForeignKey('bangumi.id'), nullable=False)
    episode_id = Column(postgresql.UUID(as_uuid=True), ForeignKey('episodes.id'), nullable=False)

    file_name = Column(String, nullable=True)
    file_path = Column(String, nullable=True)  # file path is real path to the file in filesystem
    # deprecated
    torrent_id = Column(String, nullable=True)  # torrent_id is deluge torrent id associated with this file, for imported file, torrent_id should be null

    task_id = Column(String, nullable=True)  # DownloadTaskMessage Id
    download_url = Column(String, nullable=True)  # torrent download url, can be magnet
    status = Column(Integer, nullable=False, default=1)

    resolution_w = Column(Integer, nullable=True)
    resolution_h = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)  # unit is millisecond
    label = Column(String, nullable=True)  # label can be set by admin

    episode = relationship('Episode', back_populates='video_files')
    bangumi = relationship('Bangumi', back_populates='video_files')

    STATUS_DOWNLOAD_PENDING = 1
    STATUS_DOWNLOADING = 2
    STATUS_DOWNLOADED = 3
