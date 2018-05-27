#!/usr/bin/env python

# Use this script to randomly mix trailers into one video file.
# You can use the generated video file as your pre-roll video file
# in Plex to display trailers before each movie is played.
# You must have ffmpeg installed in order to use this. Please see
# <https://github.com/FFmpeg/FFmpeg>.
#
# This script should ideally be used in conjunction with Tautulli
# notification agents to randomly re-mix the trailers each time a
# movie is played. Please see <https://github.com/Tautulli/Tautulli>
# and <https://github.com/Tautulli/Tautulli-Wiki/wiki/Custom-Scripts>
# for more information on setting this up.
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

import json
import random
import logging
import os
import os.path
from shared import validate_settings
from shared import get_config_values
from shared import get_settings
from shared import get_command_line_arguments
from shared import configure_logging

try:
    # For Python 3.0 and later
    from configparser import SafeConfigParser
    from configparser import Error
    from configparser import MissingSectionHeaderError
except ImportError:
    # Fall back for Python 2.7
    from ConfigParser import SafeConfigParser
    from ConfigParser import Error
    from ConfigParser import MissingSectionHeaderError


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

    # Get downloaded trailers
    trailers = json.load(open(settings['json_file']))

    # Randomly select trailers
    selected_trailers = random.sample(range(1,int(settings['max_trailers'])+1),int(settings['quantity']))

    input_video = []

    for x in selected_trailers:
        input_video.append(trailers[str(x)])

    # Set selected trailers
    with open(settings['selected_file'], "w") as f:
        for i in input_video:
            item = i.replace("'", "\\'")
            f.write('file \'' + item + '\'' + os.linesep)
    f.close

    # Convert selected trailers into one video
    os.system('/usr/local/bin/ffmpeg -loglevel panic -y -f concat -safe 0 -i '+settings['selected_file']+' -metadata title=Coming\ Soon -c copy '+settings['output_file'])

# Run the script
if __name__ == '__main__':
    main()
