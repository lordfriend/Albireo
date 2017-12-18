#Changelog

## 2.7.1

- InfoScanner will check bangumi status and fix it before perform a scan.
- Auto change bangumi status to FINISHED when imported.
- Fix #39
- Change the procedure for deleting an episode. Now delete is immediately effecting. 
    DeleteScanner will no longer scan episode which is in pending delete status.
    If you have episode which is in pending delete status. please restore this episode and delete it again.

## 2.7.0

### Feature Add:

- Web hook, this is new feature for third party developers to make some awesome tools with push notification. it is inspired by Github web hook.
 for more detail, see the Wiki.
 
- rpc interface for commmunication between flask server and scheduler.

### Database Changes

- add two table, web hook and web hook token.

## 2.6.3

Fix bug on add bangumi, which results in a None bangumi folder

## 2.6.3-RC

Change the add bangumi service to ensure cover image is downloaded before save to database.
 
##2.6.2

Change bangumi.moe scanner, now will emit torrent url for matched items instead magnet uri. 

##2.6.1

Add type parameter in admin/list-bangumi api and home/list-bangumi API

##2.6.0

## Feature add

- Add sentry error collector SDK for better error trace. To enable this you need to add a new config file in `config` directory.

##2.5.3

## Bug fix

- fix a bug in DeleteScanner which make it unable to delete episodes because of json.dumps cannot handle UUID

##2.5.2

## Bug fix

- the timestamp of all response use an incorrect timezone.
- the timestamp of response should be long type.


##2.5.0

## feature add

- announcement feature can be used to add announcement for client which is aim to let the operator or admin communicates with their user. A database upgrade is needed. 


##2.4.2-beta
- fix issue in DMHY scanner, sometimes DMHY return items which its enclosure entry has a url="" made the feedparser enclosure object doesn't have
 an href attribute and crash.

##2.4.1-beta

## Bug fix
- fix eps property of bangumi doesn't change when add/remove an episode.
- fix download status scanner bug

##2.4.0-beta
Redesign Image information storage. locally stored image will have their information stored in a specify table.

## Database Changes
- A new table `image` to store image information, a alembic upgrade scripts is needed. please read [database upgrade](https://github.com/lordfriend/Albireo/blob/master/alembic/README.md)
- Add new fields on Bangumi table.

## API update
- For each API that use a image url will now suggested to use a image object which contains: url, width, height, dominant_color.
For compatibility reason. the old fields will remain there.
- Add new field to bangumi management APIs. `created_by`, `mantained_by` and `alert_timeout`. These fields will work with a new 
scanner which daily check the download status of all episode make sure they are up to date. if any of the episode is behind schedule
 of over the `alert_timeout` day. an email will be sent to the `maintained_by` user. If `maintained_by` is not set, all admin
 will receive an alert mail.
- Add minlevel to user management API.


## Bug fix

- fix #64
- fix video thumbnail capture return path, should return the output capture path instead of video path. PLEASE RUN `python tools.py --cover` TO FIX THIS.

##2.3.0-beta
Enhance my_bangumi api, now it accept a search parameter `status` which is an integer represents the status of favorite.
default status is 3 (Watching) which will maintain the backward compatibility.

##2.2.1-beta

Add case-insensitive support for search bangumi API (include /api/admin/bangumi)
Add missing field `cover` in my_bangumi API.

##2.2.0-beta

Add new API for client synchronizing watch history with server with multiple items, this API provide ability for client 
reducing API call for synchronizing history.

No database changes


##2.1.1-beta

Fix a bug when get_dominant_color raise an error, the update scripts will interrupted.

##2.1.0-beta

Add dominant color extraction for bangumi cover image and episode thumbnail image.

## New Dependencies

To support color extraction. color-thief.py is added which need the following dependencies

- `python-imaging`  a system dependency that can be installed via `apt-get install python-imaging`.
- `colorthief`  a python dependency that can be installed via `pip install colorthief`  

## API Update

- bangumi object adds a new field reflecting the bangumi table change, cover_color, which is a hex string represents the dominant color for
cover image.

- episode object adds a new field reflrecting the episodes table change, thumbnail_color, which is a hex string represents the dominant color
 for thumbnail image of certain episode.
 
## Database Changes

- bangumi table add a varchar column `cover_color`
- episodes table add a varchar column `thumbnail_color`

## Update Guide

1. Install python-imaging via `apt-get install python-imaging` then install colorthief via `pip install colorthief`
2. run [database upgrade](https://github.com/lordfriend/Albireo/blob/master/alembic/README.md)
3. update your client to the latest version which will support this feature.


##2.0.0-beta

From this version. There are a lot of changes brought to User API. reset password by invite code is no longer supported. a email is required for
each registered user. A user center is added to home page for user to update email and password. Any future user related configuration can be placed
 in the user center.
 
## New API:

- email update API, allow login user update their email, currently no password verification needed but maybe added in the future.

- email confirm API, when user register or update email address, an email address confirm mail will be sent to user's email address which contains 
 a token in a link, client should implement a endpoint which path is /email/confirm that post token into this API to complete the confirm flow.
 
- request reset password API, client can provide an email address to request a password reset operation, an email will be sent to user email address if 
 it's a valid and confirmed email address. user can use that link which contains a token to set new password.
 
## Breaking Changes

- register API now require email address and will send an email to confirm that address. return 201 {"message": "ok"} when success
- update password API change it path from `update_pass` to `update-pass`, once this operation success, a notification mail will be sent to user
 email address.
- reset password API no longer use a invite code and username to validate user identity, it now use a token with new password to directly reset password
 a token is generated by request reset password API. This API also changes it path from `reset_pass` to `reset-pass`
- get user information api add two field: email and email_confirmed

## Bugfix

- Bangumi status now will be automatically updated to FINISHED when all episodes of that bangumi is in DOWNLOADED status.

## Database Changes

- users table add new field: email, email_confirmed, register_time, update_time, to update table, use [alembic script](https://github.com/lordfriend/Albireo/blob/master/alembic/README.md)
- upgrade password hash method from sha1 to sha256, old password is compatible.

### Upgrade Guide

1. Update code
2. Copy new section from config/config-sample.yml to config/config.yml, set those property to a proper value.
3. Upgrade database using [alembic script](https://github.com/lordfriend/Albireo/blob/master/alembic/README.md)
4. Upgrade your client to the latest release.

##1.1.0-beta

Add Video Files CRUD api

##1.0.1-beta

Change the default order_by value in list_bangumi of home api

##1.0.0-beta
Add delete bangumi and episode ability to admin API. these delete operation is managed by task. A task is a database record contains progress, status and type information. It can be resume
 from a interruption.
 
Add unique constraints to bangumi table `bgm_id` column. Make sure you don't have any duplicate record of bgm_id in bangumi table before you execute a database upgrade. 

Add user management api

Add bangumi.moe support, this crawler support multi files download from one torrent.

From this version, torrentfile and feed tables are no longer used. run alembic upgrad will automatically migrate data into video_file table. make sure you don't have on downloading files
before upgrade, those files will not be migrated.

## Database changes:

- Add delete_mark column on both bangumi and episode table.
- Add task table to manage delete operation.
- Deprecated torrentfile, feed table. Add new table video_file to represent download file. this table can represent the download file as three different status.

## API Changes:

get bangumi of admin api add a special parameter value to count that is -1. when count = -1, this api will return all data


##0.9.0-alpha

## Database changes:

Add two new table watch_progress and favorites, to save bangumi favorite status and watch progress of an episode.

## Bug fix

#26

fix an issue when the episode number is not started from 1 by add an eps_no_offset column into bangumi table and using this offset to correct the episode number when parsing feed. 

## NEW API

Adds some favorites and watch progress APIs. For detail, see routes.watch.

also modified some old APIs, add watch_progress to each episode returned by episdoe_detail and bangumi_detail API.


##0.8.0-alpha

## Database changes:

Add a new table 'server_session' for persist session on database. may fix the occasionally 401 issues.
TO UPDATE TABLE, read the [update document](https://github.com/lordfriend/Albireo/blob/master/alembic/README.md).

## Bug fix

- fix the always empty issues when add new bangumi caused by bgm.tv anti-bot mechanism

##0.7.0-alpha

## Database changes:

Add a new table `feed` is added for the new scheduler, besides, rss, regex in `bangumi` table is no longer used. Two columns `dmhy` and `acg_rip` are added to `bangumi` table.

TO UPDATE TABLE, read the [update document](https://github.com/lordfriend/Albireo/blob/master/alembic/README.md).

##NEW API:

Add two api for add dmhy and acg.rip keywords.

##New Scheduler

The new scheduler will individual task for each site, each task takes the feed periodically and save its find into feed table. A scanner will scan the feed table every 30 seconds.


##0.6.0-alpha

## Features Add

- InfoScanner for scanning missing information (name, name_cn, duration) and auto fill those information from bangumi.tv, note that the name_cn is not always filled.

## Bug fix

- rollback session when db connection lost

NOTE: this release require use to update their config.yml.

##0.4.0-alpha

## Features Add

- Add a CLI command to download bangumi cover image

## Breaking Changes

- Now, all client bangumi image will use bangumi.cover to get the cover image. if your see a broken image, using `tools.py --cover` to download missing bangumi cover.


##0.3.0-alpha

## Features Add

- New API:
    - on_air which list all bangumi currently on air,
    - bangumi_detail which get an bangumi detail, this api is the same api of admin bangumi detail but without admin permission
    - list_bangumi which is almost the same with admin api list bangumi

- Docker support


## Other changes

- default auto generated thumbnail is set to 00:00:01.000 frame


##0.2.0-alpha

## Features Add

- Home api for end user
- Episodes api for managing episodes
- Alembic SQLAlchemy migrate tool for migrate database
- Vagrant support for a quickly deployment with Vagrant
- Episode thumbnail generation
- Bangumi cover now will downloaded to local server

## Breaking Changes
- get bangumi api now return all episodes of this bangumi. access it with `episodes` field
- init db using sql script is not recommended, using tools.py to init db.
- ffmpeg is now a dependency to generate thumbnail for episode
- server.py now only used in development, when deploying in production, use `twistd -n web --port 5000 --wsgi appd.app`
