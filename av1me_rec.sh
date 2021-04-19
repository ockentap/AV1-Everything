#!/bin/sh
###################################################################################################
#
# av1me_rec.sh - Shell Script to Recursively Encode Videos with AV1 Codec
#
# This script looks for encodable video files in a directory
# and uses the av1me.sh script to create .webm AV1 videos.
#
# Author: Dennis Rohner (@midzer)
# URL: https://github.com/midzer/av1me
#
# License: MIT
#
# Version 0.1
#
###################################################################################################

# Enter "/path/to/av1me.sh" script
av1me="./av1me.sh"

# Define, which files are to be encoded
encodable="mp4|mkv"

# Enter directory to start (recursively) looking for encodable files
dir="/path/to/files"

find $dir -regextype posix-extended -regex ".*\.($encodable)" -exec sh -x $av1me {} \;
