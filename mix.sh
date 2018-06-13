#!/bin/bash

# Exit on error
set -e

# Get python path
python_path=$(sed -n 's/^python_path=//p' settings.cfg)

# Mix trailers
"$python_path" mix.py

exit
