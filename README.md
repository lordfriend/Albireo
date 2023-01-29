# Albireo
A bangumi auto download and management project
This is the backend part.

**This repository is archived, the project is suceeded by project-mira: **

## Motivation

There are an existed resolution for auto download bangumi from dmhy or other bt site by using flexget to parse the rss feed periodically. but that resolution is hard to manage the downloaded
file when the number of bangumi is growing. So I write this project to make the same way to auto download bangumi but associate the downloaded file with information provided by bangumi.tv.
further more, the information can be used for more user friendly function.

[Installation](#installation)

[Server](#server)

[Run with Docker](https://github.com/lordfriend/Albireo/blob/master/docker-sample/README.md)

[Nginx Configuration](#nginx-configuration)

[Scheduler](#scheduler)

[HTTP API](http://docs.albireo.apiary.io/)

[Upgrade From Old Version](https://github.com/lordfriend/Albireo/blob/master/alembic/README.md)

[Client Apps](#client-apps)

[Sentry](#sentry)

## Installation

requirements: python 2.7, deluge ( >= 1.3.13 ), postgresql 9.3 and above, ffmpeg, nodejs, python-imaging

### dependencies:

- SQLAlchemy 1.0
- psycopg2
- flask 0.10
- flask-login 0.0.3
- PyYAML
- Twisted
- feedparser
- service_identity
- requests > 2.4.2
- alembic
- subprocess32
- cfscrape
- Flask-Mail
- colorthief
- raven
- bleach

NOTE: ffmpeg is presume accessible with `ffmpeg` command

### config file

Setup your config file by copying the `config/config-sample.yml` to `config/config.yml`, then modify the database and deluge config on demand

There are some config that must be modified before your run the project

- download
    - location this is the default location of downloaded file, you should set this **absolute path** to your own download directory which your application and deluge has the permission to write

- app_secret_key this is used by flask to encrypt session for security reason

- app_secret_password_salt this is used for generate some token with hash salt

- site site related information
    - name will be appeared in some email template
    - host will be used for link in email
    - protocol will be used for link in email
    
- mail used by Flask-Mail.

### init database

using tools.py in the root directory of this project to init db

```bash
$ python tools.py --db-init # create tables if not exists

$ python tools.py --user-add admin 1234  # admin is username 1234 is password

$ python tools.py --user-promote admin 3  # admin is username 3 is the level, currently means super user
```

### set your server locale

To avoid some unicode issues, it is recommended to set locale of your server

## Server

the server is a flask app which provide http API for management and end user page (currently not completed).

In development mode, using flask built-in server:

run `python server.py`, if you set the environment variable DEBUG=True, the debug info will be print to log

In production mode, using twistd as WSGI container

```shell
twistd -n web --port 5000 --wsgi appd.app
```

## Nginx Configuration

To serve the static files like images and videos, you need to setup a static file server, we recommend using nginx.
Here are nginx configurations.

**You need to serve the following url pattern.**

- bangumi cover: `{http|https}://{youdomain}/pic/{bangumi_id}/cover.jpg`
- episode thumbnail: `{http|https}://{youdomain}/pic/{bangumi_id}/thumbnails/{episode_no}.png`
- video: `{http|https}://{youdomain}/video/{bangumi_id}/{path_to_video}`

**explanation**
- yourdomain is the configured domain in `config/config.yml` file `domain` section
- bangumi_id is the bangumi id which is a uuid string
- episode_no is the episode number for certain episode
- path_to video is video file path relative to download path which configured in your config file.

In fact, you just need to take the path part after `/pic/` and append to your download location. the actual file is there.

For example your download path is `/path/to/videos` which is set in `config/config.yml` download location section

```nginx
server {
	listen 8000 default_server;
	
	root /path/to/videos;
	
	server_name localhost;
	
	location ~ ^(?:/pic|/video)/(.+) {
		try_files /$1 $uri =404;
	}
}
```

According to your environment and configuration, the nginx configuration may different from this example.


### Scheduler

Scheduler is the core of this project ,it work like an cron daemon and periodically visit the bangumi table to see if there are episode need to be downloaded.

To run Scheduler, run `python scheduler.py` is enough, if you set environment variable DEBUG to True, debug info will be printed.

Usage:

You need to add some keywords in the admin bangumi detail page for the site you want scan. currently dmhy and acg.rip are supported. the rule for keywords can be found in
 corresponding site's help document.


## Client Apps

### Official

Web App + Admin Console: https://github.com/lordfriend/Deneb

### Community

#### Android App

[Megumin](https://github.com/RoyaAoki/Megumin) contains all function except the admin console. support Android TV and mobile. 

[![Get On Google Play](https://play.google.com/intl/en_us/badges/images/badge_new.png)](https://play.google.com/store/apps/details?id=com.sqrtf.megumin)

[Mana](https://github.com/WindFi/mana) Android client for Albireo.Use todo-mvp pattern

[![Get On Google Play](https://play.google.com/intl/en_us/badges/images/badge_new.png)](https://play.google.com/store/apps/details?id=me.sunzheng.mana)


## Sentry

If you are developer, you may want to receive and collect crash log. This function is already integrated. We use [Sentry](https://sentry.io) to collect crash log
 and make an alert to developer.
 
To enable Sentry, you need copy and rename `config/sentry-sample.yml` to `config/sentry.yml` and then modify the `web_api` and `scheduler`
 to your own DSN. It is suggested using different dsn for each one, but use the same is ok.
