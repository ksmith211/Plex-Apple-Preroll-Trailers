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
    settings = get_settings()
    trailers={}
    i = 0
    for line in new_list:
        item = line.strip()
        i = i + 1
        trailers[i] = settings['download_dir']+"/"+item
    with open(settings['json_file'], 'w') as f:
        json.dump(trailers, f)
    f.close


def record_downloaded_file(filename, dl_list_path):
    # Append downloaded filename to the text file
    file_list = get_downloaded_files(dl_list_path)
    file_list.append(filename)
    write_downloaded_files(file_list, dl_list_path)


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


def convert_resolution(trailer_file_name, destdir, res):
    # Check resolution and convert video if it does not conform to correct size
    if res == '480':
        target_width = '848'
        target_height = '480'
    elif res == '720':
        target_width = '1280'
        target_height = '720'
    elif res == '1080':
        target_width = '1920'
        target_height = '1080'

    # Check if dimensions match target sizes
    size = os.popen('/usr/local/bin/ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "'+destdir+'/'+trailer_file_name+'"').read()
    size = str(size).rstrip()
    dimensions = size.split('x')
    if (dimensions[0] != target_width or dimensions[1] != target_height):
        logging.debug("  Incompatible resolution. Converting")
        os.system('/usr/local/bin/ffmpeg -loglevel panic -i "'+destdir+'/'+trailer_file_name+'" -vf "scale='+target_width+':'+target_height+':force_original_aspect_ratio=decrease,pad='+target_width+':'+target_height+':(ow-iw)/2:(oh-ih)/2" "'+destdir+'/output.mov"')
        os.system('mv "'+destdir+'/output.mov" "'+destdir+'/'+trailer_file_name+'"')


def download_trailers_from_page(page_url, dl_list_path, res, destdir, types):
    # Downloads trailer from page URL
    logging.debug('Checking for files at ' + page_url)
    trailer_urls = get_trailer_file_urls(page_url, res, types)
    downloaded_files = get_downloaded_files(dl_list_path)
    for trailer_url in trailer_urls:
        trailer_file_name = get_trailer_filename(trailer_url['title'], trailer_url['type'],
                                                 trailer_url['res'])
        if trailer_file_name not in downloaded_files:
            logging.info('Downloading ' + trailer_url['type'] + ': ' + trailer_file_name)
            download_trailer_file(trailer_url['url'], destdir, trailer_file_name)
            convert_resolution(trailer_file_name, destdir, res)
            record_downloaded_file(trailer_file_name, dl_list_path)
        else:
            logging.debug('*** File already downloaded, skipping: ' + trailer_file_name)


def get_trailer_filename(film_title, video_type, res):
    # Convert filenames
    trailer_file_name = u''.join(s for s in film_title if s not in r'\/:*?<>|#%&{}$!\'"@+`=')
    trailer_file_name = re.sub(r'\s\s+', ' ', trailer_file_name)
    trailer_file_name = trailer_file_name.strip() + '.' + video_type + '.' + res + u'p.mov'
    return trailer_file_name


def validate_settings(settings):
    # Validate provided settings
    valid_resolutions = ['480', '720', '1080']
    valid_video_types = ['single_trailer', 'trailers', 'all']
    valid_output_levels = ['debug', 'downloads', 'error']

    required_settings = ['resolution', 'download_dir', 'video_types', 'output_level', 'list_file', 'json_file', 'selected_file', 'output_file', 'max_trailers', 'quantity']

    for setting in required_settings:
        if setting not in settings:
            raise ValueError("cannot find value for '{}'".format(setting))

    if settings['resolution'] not in valid_resolutions:
        res_string = ', '.join(valid_resolutions)
        raise ValueError("invalid resolution. Valid values: {}".format(res_string))

    if not os.path.exists(settings['download_dir']):
        raise ValueError('the download directory must be a valid path')

    if settings['video_types'].lower() not in valid_video_types:
        types_string = ', '.join(valid_video_types)
        raise ValueError("invalid video type. Valid values: {}".format(types_string))

    if settings['output_level'].lower() not in valid_output_levels:
        output_string = ', '.join(valid_output_levels)
        raise ValueError("invalid output level. Valid values: {}".format(output_string))

    if not os.path.exists(os.path.dirname(settings['list_file'])):
        raise ValueError('the list file directory must be a valid path')

    if not os.path.exists(os.path.dirname(settings['json_file'])):
        raise ValueError('the json file directory must be a valid path')

    if not os.path.exists(os.path.dirname(settings['selected_file'])):
        raise ValueError('the selected file directory must be a valid path')

    if not os.path.exists(os.path.dirname(settings['output_file'])):
        raise ValueError('the output file directory must be a valid path')

    return True


def get_config_values(config_path, defaults):
    # Get settings from config file

    try:
        # For Python 3.0 and later
        from configparser import ConfigParser
    except ImportError:
        # Fall back for Python 2.7 naming
        from ConfigParser import SafeConfigParser as ConfigParser

    config = ConfigParser(defaults)
    config_values = config.defaults()

    config_paths = [
        config_path,
        os.path.join(os.path.expanduser('~'), '.trailers.cfg'),
    ]

    config_file_found = False
    for path in config_paths:
        if os.path.exists(path):
            config_file_found = True
            config.read(path)
            config_values = config.defaults()
            break

    if not config_file_found:
        logging.info('Config file not found. Using default values.')

    return config_values


def get_settings():
    # Validate and return provided settings

    script_dir = os.path.abspath(os.path.dirname(__file__))
    defaults = {
        'download_dir': script_dir,
        'resolution': '720',
        'video_types': 'single_trailer',
        'output_level': 'debug',
    }

    args = get_command_line_arguments()

    config_path = "{}/settings.cfg".format(script_dir)
    if 'config_path' in args:
        config_path = args['config_path']

    config = get_config_values(config_path, defaults)

    settings = config.copy()
    settings.update(args)

    settings['download_dir'] = os.path.expanduser(settings['download_dir'])
    settings['config_path'] = config_path

    if ('list_file' not in args) and ('list_file' not in config):
        settings['list_file'] = os.path.join(
            settings['download_dir'],
            'download_list.txt'
        )

    settings['list_file'] = os.path.expanduser(settings['list_file'])

    validate_settings(settings)

    return settings


def get_command_line_arguments():
    # Dictionary of command line arguments
    
    import argparse

    parser = argparse.ArgumentParser(
        description='Download movie trailers from the Apple website. With no arguments, will' +
        'download all of the trailers in the current "Just Added" list. When a trailer page ' +
        'URL is specified, will only download the single trailer at that URL. Example URL: ' +
        'http://trailers.apple.com/trailers/lions_gate/thehungergames/'
    )

    parser.add_argument(
        '-c, --config',
        action='store',
        dest='config',
        help='The location of the config file. Defaults to "settings.cfg"' +
        'in the script directory.'
    )

    parser.add_argument(
        '-d, --dir',
        action='store',
        dest='dir',
        help='The directory to which the trailers should be downloaded. ' +
        'Defaults to the script directory.'
    )

    parser.add_argument(
        '-l, --listfile',
        action='store',
        dest='filepath',
        help='The location of the download list file. The names of the ' +
        'previously downloaded trailers are stored in this file. ' +
        'Defaults to "download_list.txt" in the download directory.'
    )

    parser.add_argument(
        '-r, --resolution',
        action='store',
        dest='resolution',
        help='The preferred video resolution to download. Valid options are ' +
        '"1080", "720", and "480".'
    )

    parser.add_argument(
        '-u, --url',
        action='store',
        dest='url',
        help='The URL of the Apple Trailers web page for a single trailer.'
    )

    parser.add_argument(
        '-v, --videotypes',
        action='store',
        dest='types',
        help='The types of videos to be downloaded. Valid options are ' +
        '"single_trailer", "trailers", and "all".'
    )

    parser.add_argument(
        '-o, --output_level',
        action='store',
        dest='output',
        help='The level of console output. Valid options are ' +
        '"debug", "downloads", and "error".'
    )

    results = parser.parse_args()
    args = {
        'config_path': results.config,
        'download_dir': results.dir,
        'list_file': results.filepath,
        'page': results.url,
        'resolution': results.resolution,
        'video_types': results.types,
        'output_level': results.output,
    }

    # Remove all pairs that were not set on the command line
    set_args = {}
    for name in args:
        if args[name] is not None:
            set_args[name] = args[name]

    return set_args


def configure_logging(output_level):
    # Configure logging
    
    output_level = output_level.lower()

    log_level = logging.DEBUG
    if output_level == 'downloads':
        log_level = logging.INFO
    elif output_level == 'error':
        log_level = logging.ERROR

    logging.basicConfig(format='%(message)s')
    logging.getLogger().setLevel(log_level)


def load_json_from_url(url):
    # Load json file from provided URL
    response = urlopen(url)
    str_response = response.read().decode('utf-8')
    return json.loads(str_response)


def main():
    # Run the script
    
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

    # Delete the previously downloaded files
    os.chdir(settings['download_dir'])
    os.system('rm *.mov')

    # Delete extra files
    os.chdir(settings['main_dir'])
    os.system('rm downloads.txt')
    os.system('rm trailers.json')
    os.system('rm selected.txt')

    # Do the download
    if 'page' in settings:
        # The trailer page URL was passed in on the command line
        download_trailers_from_page(
            settings['page'],
            settings['list_file'],
            settings['resolution'],
            settings['download_dir'],
            settings['video_types']
        )

    else:
        # Get trailers from feed
        feed_url = 'https://trailers.apple.com/itunes/us/json/most_pop.json'
        get_trailers = load_json_from_url(feed_url)

        # Box office trailers
        box_office_trailers = get_trailers['items'][1]['thumbnails']
        for trailer in box_office_trailers:
            url = 'http://trailers.apple.com' + trailer['url']
            download_trailers_from_page(
                url,
                settings['list_file'],
                settings['resolution'],
                settings['download_dir'],
                settings['video_types']
            )
            dl_list = io.open(settings['list_file'], mode='r', encoding='utf-8')
            i = 0
            for line in dl_list:
                i = i + 1    
            if i >= (int(settings['max_trailers']) / 2):
                break
            
        # Most popular trailers
        most_popular_trailers = get_trailers['items'][0]['thumbnails']
        for trailer in most_popular_trailers:
            url = 'http://trailers.apple.com' + trailer['url']
            download_trailers_from_page(
                url,
                settings['list_file'],
                settings['resolution'],
                settings['download_dir'],
                settings['video_types']
            )
            dl_list = io.open(settings['list_file'], mode='r', encoding='utf-8')
            i = 0
            for line in dl_list:
                i = i + 1    
            if i >= int(settings['max_trailers']):
                break
            
# Run the script
if __name__ == '__main__':
    main()
