#!/bin/sh
###################################################################################################
#
# av1me.sh - Shell Script to Encode Videos with AV1 Codec
#
# This script creates AV1 videos (.webm) from original video files.
# Right now, MP4 and mkv are supported input file types.
# You can specify an video quality for the conversion.
#
# Author: Dennis Rohner (@midzer)
# URL: https://github.com/midzer/av1me
#
# License: MIT
#
# Version 0.1
#
###################################################################################################

# Set quality [0-63]
quality=42

# Determine size of original file
origFile="$1"
origFileSize=$(stat -c %s "$origFile")

# Let's start!
echo "Processing $origFile ..."
ffmpeg -i $origFile -c:v libaom-av1 -crf $quality -b:v 0 -strict -2 ${origFile%.*}.webm

# How did we perform?
av1edFileSize=$(stat -c %s "${origFile%.*}.webm")
percent=$((100 - av1edFileSize * 100 / origFileSize))
percent=$( printf '%d' $percent )

result="File size reduced by "
result=$result$percent
result="$result percent"
echo $result
