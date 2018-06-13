# Plex-Apple-Preroll-Trailers

A set of python scripts for downloading trailers from Apple, randomly mixing them into one video file, and playing them before movies in Plex as a preroll trailer.

## Getting Started

These instructions will help you set up your Plex Media Server to download new trailers once per week and randomly select and mix new trailers each time a movie is played so you always have new trailers to watch each time you watch a new movie.

## Prerequisites

**Plex Media Server**

This goes without saying but if you aren't already using Plex to organize and play your media files, you're probably in the wrong place.

**Python**

In order to use these scripts, you'll need to be running Python 2.x or higher.

**ffmpeg**

You'll also need to have ffmpeg installed in order to convert videos into a uniform size and mix them into one video file for Plex (https://www.ffmpeg.org/). This is easy to install with Homebrew.

```
brew update
brew install ffmpeg --with-tools --with-fdk-aac --with-libvpx --with-x265
```

**Tautulli (recommended)**

If you want to randomly mix the trailers each time a movie is played in Plex, you'll need to have Tautulli installed on your Plex Media Server (https://github.com/Tautulli/Tautulli). It is possible to avoid this step if you would prefer to just mix the trailers a few times a day via a cron job but, let's face it, that isn't nearly as awesome. Plus, if you found your way here, you'll probably enjoy all of the great things Tautulli has to offer as well.

## Installation

**Clone**

The first step is to clone the repository somewhere onto your Plex Media Server. It doesn't really matter where but you'll need to add the name of the directory to settings.cfg under "main_dir" once you've finished.

**Settings**

Next, take a look at the other options in settings.cfg. Most of these settings don't really need to be altered but the important ones are "python_path" (the path to python), "ffmpeg_path" (the path to ffmpeg), "main_dir" (the directory the scripts are located in), "max_trailers" (the maximum number of trailers that should be downloaded to your server at any given time), "quantity" (the number of trailers that should be mixed and shown before each movie), and "resolution" (the resolution you would like the trailers to be downloaded in).

**Download Script**

Next, open the crontab.

```
crontab -e
```

In this file you need to add a job for downloading new trailers once per week. You can tell the script to download new trailers as often as you would like but I find that once per week is totally sufficient if you have "max_trailers" set to a decent value like 30. The following example will download trailers every Friday at 3:30am. If you would like to customize the frequency and don't feel comfortable with scheduling jobs, you can use https://crontab.guru. Be sure to change the paths to python and download.py to wherever they are located on your machine and save the file when you're done.

```
30 3 * * fri /path/to/python /path/to/scripts/download.py 2>&1
```

**Mix Script**

The next step is to set up the script for randomly mixing the trailers into one video file so that they can be played as a preroll trailer in Plex.

*If you want to use Tautulli (recommended):*

Open up Tautulli and go to Settings. In the "Notifications Agents" section, create a new script. For the "Script Folder", add `/path/to/scripts` (change the path to the directory you put the scripts in) and for the "Script File" use `./mix.py`. Add a description and then switch over to the "Triggers" tab and check "Playback Start." Next, go to the "Conditions" tab to tell Tautulli when the script should be fired. I am using a condition for when "Media Type" is "movie." Save it and you're all done with Tautulli.

*If you don't want to use Tautulli (optional):*

Open the crontab again.

```
crontab -e
```

Add an entry for mix.py. This example will run the script every 8 hours but you can customize the frequency to whatever your preference is. Be sure to change the paths to python and mix.py to wherever they are located on your machine and save the file when you're done.

```
0 */8 * * * /path/to/python /path/to/scripts/mix.py 2>&1
```

**Plex Media Server**

Now you need to tell Plex to use the video file that mix.sh generates as the preroll trailer. Open Plex and navigate to Settings > Server > Extras and add the location of the video file to "Cinema Trailers pre-roll video." If you didn't change the name of the "output_file" in settings.cfg, you can use the example below. Be sure to change the path to the directory you put the scripts in.

```
/path/to/scripts/Trailers.mp4
```

## Running For The First Time

Since you just set up the scripts for the first time, you don't have any trailers downloaded yet and I doubt you want to wait until the next time 3:30am rolls around on a Friday :). Therefore, you need to manually run the scripts one time. Via the command line, navigate to the directory you put the scripts in and run the download.py script. Once it finishes, run the mix.py script.

```
/path/to/python download.py
/path/to/python mix.py
```

Please note that it will take a long time to download and convert all of the videos for the first time but future runs will be much faster since the script will never re-download any trailer that has already been downloaded. If you would like to watch what's happening, you can set the "output_level" to "debug" in settings.cfg before running it, but this is not necessary.

Enjoy!

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.