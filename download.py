#!/usr/bin/env python

# Use this script to download trailers from Apple.
# This script should be set up as a cron job and ran once per
# week in order to continually fetch new trailers.
#
# You must have ffmpeg installed in order to use this. Please see
# <https://github.com/FFmpeg/FFmpeg>.
#
# This script should also be used in conjunction with mix.py to
# randomly mix the downloaded trailers into one video file that
# can be used as a pre-roll video file in Plex for displaying
# trailers before each movie is played.
#
# Settings should be configured in settings.cfg.

# Copyright 2018 David Engel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import io
import json
import logging
import os.path
import re
import shutil
import socket
from shared import validate_settings
from shared import get_config_values
from shared import get_settings
from shared import get_command_line_arguments
from shared import configure_logging

try:
    # For Python 3.0 and later
    from configparser import Error
    from configparser import MissingSectionHeaderError
    from urllib.request import urlopen
    from urllib.request import Request
    from urllib.error import HTTPError
    from urllib.error import URLError
except ImportError:
    # Fall back for Python 2.7
    from ConfigParser import Error
    from ConfigParser import MissingSectionHeaderError
    from urllib2 import urlopen
    from urllib2 import Request
    from urllib2 import HTTPError
    from urllib2 import URLError


def get_trailer_file_urls(page_url, res, types):
    # Get trailer file URLs
    urls = []
    film_data = load_json_from_url(page_url + '/data/page.json')
    title = film_data['page']['movie_title']
    apple_size = map_res_to_apple_size(res)
    for clip in film_data['clips']:
        video_type = clip['title']
        if apple_size in clip['versions']['enus']['sizes']:
            file_info = clip['versions']['enus']['sizes'][apple_size]
            file_url = convert_src_url_to_file_url(file_info['src'], res)
            if should_download_file(types, video_type):
                url_info = {
                    'res': res,
                    'title': title,
                    'type': video_type,
                    'url': file_url,
                }
                urls.append(url_info)
        elif should_download_file(types, video_type):
            logging.error('*** No %sp file found for %s', res, video_type)
    if types == 'single_trailer':
        final = []
        length = len(urls)
        if length > 1:
            final.append(urls[length-1])
            return final
        else:
            return urls
    else:
        return urls


def map_res_to_apple_size(res):
    # Trailer resolution mapping
    res_mapping = {'480': u'sd', '720': u'hd720', '1080': u'hd1080'}
    if res not in res_mapping:
        res_string = ', '.join(res_mapping.keys())
        raise ValueError("Invalid resolution. Valid values: %s" % res_string)
    return res_mapping[res]


def convert_src_url_to_file_url(src_url, res):
    # Convert video source URL to actual file URL on server
    src_ending = "_%sp.mov" % res
    file_ending = "_h%sp.mov" % res
    return src_url.replace(src_ending, file_ending)


def should_download_file(requested_types, video_type):
    # Check if trailer should be downloaded
    do_download = False
    requested_types = requested_types.lower()
    video_type = video_type.lower()
    if requested_types == 'all':
        do_download = True
    elif requested_types == 'single_trailer':
        do_download = (video_type.startswith('trailer'))
    elif requested_types == 'trailers':
        if (video_type.startswith('trailer') or
                video_type.startswith('teaser') or
                video_type == 'first look'):
            do_download = True
    return do_download


def get_downloaded_files(dl_list_path):
    # Get list of downloaded files from list in text file
    file_list = []
    if os.path.exists(dl_list_path):
        utf8_file = io.open(dl_list_path, mode='r', encoding='utf-8')
        for line in utf8_file:
            file_list.append(line.strip())
        utf8_file.close()
    return file_list


def write_downloaded_files(file_list, dl_list_path):
    # Write list of downloaded files to text file
    new_list = [filename + u'\n' for filename in file_list]
    downloads_file = io.open(dl_list_path, mode='w', encoding='utf-8')
    downloads_file.writelines(new_list)
    downloads_file.close()


def record_downloaded_file(filename, dl_list_path):
    # Append downloaded filename to the text file
    file_list = get_downloaded_files(dl_list_path)
    file_list.append(filename)
    write_downloaded_files(file_list, dl_list_path)


def create_json_file(list_file, download_dir, json_file):
    # Create json file of downloaded trailers
    downloaded_trailers = get_downloaded_files(list_file)
    trailers={}
    i = 1
    for item in downloaded_trailers:
        trailers[i] = download_dir+"/"+item
        i = i + 1
    with open(json_file, 'w') as f:
        json.dump(trailers, f)
    f.close


def delete_old_trailers(trailers, list_file, download_dir):
    downloaded_files = get_downloaded_files(list_file)
    for item in downloaded_files:
        if item not in trailers:
            item = item.replace(' ', '\ ')
            logging.debug("*** File no longer necessary. Deleting "+item)
            os.remove(download_dir+'/'+item)
    write_downloaded_files(trailers, list_file)


def download_trailer_file(url, destdir, filename):
    # Download the trailer file from the URL
    # Spoof the user agent
    # Resume partial downloads and skip already downloaded files
    file_path = os.path.join(destdir, filename)
    file_exists = os.path.exists(file_path)

    existing_file_size = 0
    if file_exists:
        existing_file_size = os.path.getsize(file_path)

    data = None
    headers = {'User-Agent': 'Quick_time/7.6.2'}

    resume_download = False
    if file_exists and (existing_file_size > 0):
        resume_download = True
        headers['Range'] = 'bytes={}-'.format(existing_file_size)

    req = Request(url, data, headers)

    try:
        server_file_handle = urlopen(req)
    except HTTPError as ex:
        if ex.code == 416:
            logging.debug("*** File already downloaded, skipping")
            return
        elif ex.code == 404:
            logging.error("*** Error downloading file: file not found")
            return

        logging.error("*** Error downloading file")
        return
    except URLError as ex:
        logging.error("*** Error downloading file")
        return

    chunk_size = 1024 * 1024

    try:
        if resume_download:
            logging.debug("  Resuming file %s", file_path)
            with open(file_path, 'ab') as local_file_handle:
                shutil.copyfileobj(server_file_handle, local_file_handle, chunk_size)
        else:
            logging.debug("  Saving file to %s", file_path)
            with open(file_path, 'wb') as local_file_handle:
                shutil.copyfileobj(server_file_handle, local_file_handle, chunk_size)
    except socket.error as ex:
        logging.error("*** Network error while downloading file: %s", ex)
        return


def convert(trailer_file_name, destdir, res, ffmpeg_path):
    # Convert video resolution and use x264 at 24fps and aac
    if res == '480':
        target_width = '848'
        target_height = '480'
    elif res == '720':
        target_width = '1280'
        target_height = '720'
    elif res == '1080':
        target_width = '1920'
        target_height = '1080'

    logging.debug("  Converting")
    os.system(ffmpeg_path+' -loglevel panic -i "'+destdir+'/'+trailer_file_name+'" -vf "scale='+target_width+':'+target_height+':force_original_aspect_ratio=decrease,pad='+target_width+':'+target_height+':(ow-iw)/2:(oh-ih)/2" -c:v libx264 -c:a aac -r 24 "'+destdir+'/.output.mov"')
    os.rename(destdir+'/.output.mov', destdir+'/'+trailer_file_name)


def download_trailers_from_page(page_url, dl_list_path, res, destdir, types, ffmpeg_path):
    # Downloads trailer from page URL
    logging.debug('Checking for files at ' + page_url)
    trailer_urls = get_trailer_file_urls(page_url, res, types)
    downloaded_files = get_downloaded_files(dl_list_path)

    for trailer_url in trailer_urls:
        trailer_file_name = get_trailer_filename(trailer_url['title'], trailer_url['type'], trailer_url['res'])
        trailer_file_name = removeNonAscii(trailer_file_name)

        if trailer_file_name not in downloaded_files:
            logging.info('Downloading ' + trailer_url['type'] + ': ' + trailer_file_name)
            download_trailer_file(trailer_url['url'], destdir, trailer_file_name)
            convert(trailer_file_name, destdir, res, ffmpeg_path)
            record_downloaded_file(trailer_file_name, dl_list_path)
        else:
            logging.debug('*** File already downloaded, skipping: ' + trailer_file_name)

        return trailer_file_name


def get_trailer_filename(film_title, video_type, res):
    # Convert filenames
    trailer_file_name = u''.join(s for s in film_title if s not in r'\/:*?<>|#%&{}$!\'"@+`=')
    trailer_file_name = re.sub(r'\s\s+', ' ', trailer_file_name)
    trailer_file_name = trailer_file_name.strip() + '.' + video_type + '.' + res + u'p.mov'
    return trailer_file_name


def load_json_from_url(url):
    # Load json file from provided URL
    response = urlopen(url)
    str_response = response.read().decode('utf-8')
    return json.loads(str_response)


def removeNonAscii(text):
    return "".join(i for i in text if ord(i)<128)


def main():
    # Main script

    # Set default log level so we can log messages generated while loading the settings.
    configure_logging('')

    try:
        settings = get_settings()
    except MissingSectionHeaderError:
        logging.error('Configuration file is missing a header section, ' +
                      'try adding [DEFAULT] at the top of the file')
        return
    except (Error, ValueError) as ex:
        logging.error("Configuration error: %s", ex)
        return

    configure_logging(settings['output_level'])

    logging.debug("Using configuration values:")
    logging.debug("Loaded configuration from %s", settings['config_path'])
    for name in sorted(settings):
        if name != 'config_path':
            logging.debug("    %s: %s", name, settings[name])

    logging.debug("")

    # Do the download
    if 'page' in settings:
        # The trailer page URL was passed in on the command line
        download_trailers_from_page(
            settings['page'],
            settings['list_file'],
            settings['resolution'],
            settings['download_dir'],
            settings['video_types'],
            settings['ffmpeg_path']
        )

    else:
        # Get trailers from feed
        feed_url = 'https://trailers.apple.com/itunes/us/json/most_pop.json'
        get_trailers = load_json_from_url(feed_url)
        trailers = []
        count = 0

        # Box office trailers
        box_office_trailers = get_trailers['items'][1]['thumbnails']
        for trailer in box_office_trailers:
            url = 'http://trailers.apple.com' + trailer['url']
            download = download_trailers_from_page(
                url,
                settings['list_file'],
                settings['resolution'],
                settings['download_dir'],
                settings['video_types'],
                settings['ffmpeg_path']
            )
            if download:
                trailers.append(download)
                count = count + 1
            # Limit box office trailers to 60% of downloads
            if count >= (int(settings['max_trailers']) * 0.6):
                break

        # Most popular trailers
        most_popular_trailers = get_trailers['items'][0]['thumbnails']
        for trailer in most_popular_trailers:
            url = 'http://trailers.apple.com' + trailer['url']
            download = download_trailers_from_page(
                url,
                settings['list_file'],
                settings['resolution'],
                settings['download_dir'],
                settings['video_types'],
                settings['ffmpeg_path']
            )
            if download:
                trailers.append(download)
                count = count + 1
            if count >= (int(settings['max_trailers'])):
                break

        # Delete old trailers
        delete_old_trailers(trailers, settings['list_file'], settings['download_dir'])

        # Create json file of downloaded trailers for mix.py
        create_json_file(settings['list_file'], settings['download_dir'], settings['json_file'])


# Run the script
if __name__ == '__main__':
    main()
