# -*- coding: utf-8 -*-
episode_regex_tuple = (
    u'第(\d+)話', u'第(\d+)话',
    '\[(\d+)(?:v\d)?(?:\s?END)?\]',
    '\s(\d{2,})\s',
    '\s(\d+)$',
    u'【(\d+)(?:v\d)?(?:\s?END)?】',
    '[.\s]Ep(\d+)[.\s]',
    u'第(\d+)回',
    '\.S\d{1,2}E(\d{1,2})\.',
    u'第(\d+)集',
)


VIDEO_FILE_EXT = (
    '.mp4',
    '.mkv',
    '.ts',
    '.mov',
    '.webm',
    '.m2ts',
    '.m2p',
    '.ps',
    '.mpg',
    '.mpeg',
    '.avi',
    '.wmv'
)
