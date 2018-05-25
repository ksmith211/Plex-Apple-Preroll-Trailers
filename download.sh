#!/bin/bash

# Exit on error
set -e

# Download trailers
/usr/bin/python download.py

# Mix trailers
/usr/bin/python mix.py

exit
