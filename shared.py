#!/usr/bin/env python

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


def validate_settings(settings):
    # Validate provided settings
    valid_resolutions = ['480', '720', '1080']
    valid_video_types = ['single_trailer', 'trailers', 'all']
    valid_output_levels = ['debug', 'downloads', 'error']

    required_settings = ['ffmpeg_path', 'main_dir', 'download_dir', 'list_file', 'json_file', 'selected_file', 'output_file', 'max_trailers', 'quantity', 'resolution', 'video_types', 'output_level']

    for setting in required_settings:
        if setting not in settings:
            raise ValueError("cannot find value for '{}'".format(setting))

    if not os.path.isfile(settings['ffmpeg_path']):
        raise ValueError('the ffmpeg path must be a valid path')

    if not os.path.exists(settings['main_dir']):
        raise ValueError('the main directory must be a valid path')

    if not os.path.exists(settings['download_dir']):
        raise ValueError('the download directory must be a valid path')

    if not os.path.exists(os.path.dirname(settings['list_file'])):
        raise ValueError('the list file directory must be a valid path')

    if not os.path.exists(os.path.dirname(settings['json_file'])):
        raise ValueError('the json file directory must be a valid path')

    if not os.path.exists(os.path.dirname(settings['selected_file'])):
        raise ValueError('the selected file directory must be a valid path')

    if not os.path.exists(os.path.dirname(settings['output_file'])):
        raise ValueError('the output file directory must be a valid path')

    if settings['resolution'] not in valid_resolutions:
        res_string = ', '.join(valid_resolutions)
        raise ValueError("invalid resolution. Valid values: {}".format(res_string))

    if settings['video_types'].lower() not in valid_video_types:
        types_string = ', '.join(valid_video_types)
        raise ValueError("invalid video type. Valid values: {}".format(types_string))

    if settings['output_level'].lower() not in valid_output_levels:
        output_string = ', '.join(valid_output_levels)
        raise ValueError("invalid output level. Valid values: {}".format(output_string))

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
        'main_dir': script_dir,
        'download_dir': script_dir+'/downloads',
        'list_file': script_dir+'/.downloads.txt',
        'json_file': script_dir+'/.trailers.json',
        'selected_file': script_dir+'/.selected.txt',
        'output_file': script_dir+'/Trailers.mp4',
        'max_trailers': 30,
        'quantity': 3,
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

    settings['download_dir'] = os.path.join(settings['main_dir'], settings['download_dir'])
    settings['list_file'] = os.path.join(settings['main_dir'], settings['list_file'])
    settings['json_file'] = os.path.join(settings['main_dir'], settings['json_file'])
    settings['selected_file'] = os.path.join(settings['main_dir'], settings['selected_file'])
    settings['output_file'] = os.path.join(settings['main_dir'], settings['output_file'])

    settings['download_dir'] = os.path.expanduser(settings['download_dir'])
    settings['config_path'] = config_path

    if ('list_file' not in args) and ('list_file' not in config):
        settings['list_file'] = os.path.join(
            settings['main_dir'],
            '.downloads.txt'
        )

    settings['list_file'] = os.path.expanduser(settings['list_file'])

    validate_settings(settings)

    return settings


def get_command_line_arguments():
    # Dictionary of command line arguments

    import argparse

    parser = argparse.ArgumentParser(
        description='Download movie trailers from the Apple website. With no arguments, will' +
        'download trailers from the most popular feed. When a trailer page URL is specified, ' +
        'will only download the single trailer at that URL. Example URL: ' +
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
        'Defaults to ".downloads.txt" in the main directory.'
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
