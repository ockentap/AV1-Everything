#!/bin/sh
###################################################################################################
#
# av1me.sh - Shell Script to Encode Videos with AV1 Codec
#
# This script creates AV1 videos (.webm) from original video files.
# Right now, MP4 and mkv are supported input file types.
# You can specify an video quality for the conversion.
#
# (Original)Author: Dennis Rohner (@midzer)
# (Original)URL: https://github.com/midzer/av1me
# 
# Author: Ockentap (@ockentap)
# URL:https://github.com/ockentap/av1me/
# License: MIT
#
# Version 0.1
#
###################################################################################################

# Set quality [0-63]
quality=32

# Determine size of original file
origFile="$1"
origFileSize=$(stat -c %s "$origFile")

# Let's start!
echo "Processing $origFile ..."
# Change libsvtav1 to libaom-av1 (or encoder of your choosing) 
ffmpeg -i $origFile -c:v libsvtav1 -crf $quality -b:v 0 -strict -2 ${origFile%.*}.mp4

# How did we perform?
av1edFileSize=$(stat -c %s "${origFile%.*}.mp4")
percent=$((100 - av1edFileSize * 100 / origFileSize))
percent=$( printf '%d' $percent )

result="File size reduced by "
result=$result$percent
result="$result percent"
echo $result
