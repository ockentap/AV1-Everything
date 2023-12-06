#!/bin/sh
#exec >> logfile.txt 2>&1
exec >> logfile.txt
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
# URL:https://github.com/ockentap/AV1-Everything
# License: MIT
#
# Version 0.1
#
###################################################################################################

echo ----------------------------------------------------------------------------------------------------

# Date for logfile

echo Starting on $(date) ...
#------------------------------------------------------------------------------------------
#Determines if source needs to be processed

videoformat=$(ffprobe -loglevel error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$1")

if [ "$videoformat" = "av1" ]; then
echo Video $1 is alredy AV1
exit
else
continue
fi
#------------------------------------------------------------------------------------------
# Set quality [0-63]
quality=42
#------------------------------------------------------------------------------------------
# Determine size of original file
origFile="$1"
origFileSize=$(stat -c %s "$origFile")
#------------------------------------------------------------------------------------------
# Let's start!
echo "Processing $origFile ..."
ffmpeg -i $origFile -c:v libsvtav1 -crf $quality -b:v 0 -strict -2 ${origFile%.*}.mp4 -n
#------------------------------------------------------------------------------------------
# Delete source file
# echo "Deleting source ..."
# rm $origFile
#------------------------------------------------------------------------------------------
# Move Source file to a directory outside root directory for manual deletion, you can change the path but dont place it inside of the root directory else the files will be reprocessed endlessly.
# Note that only GNU mv can use the "--backup=numbered or --backup=t" argument that adds numbers to source file if a file with same name exists in desitnation folder. 
# OS's like Alpine, Artix or Voidlinux won't be able to use this feature hence why files will be renamed to Epoch time. 
  	
echo "Moving" $($origFile) "source to predetermined directory ..."

#GNU mv
mv --backup=numbered $origFile ./movedsource/"$(origFile).mp4"

#Non-GNU mv
#mkdir ../movedsource
#mv  $origFile ../movedsource/"$(date +'%s').mp4"

#------------------------------------------------------------------------------------------
# How did we perform?
av1edFileSize=$(stat -c %s "${origFile%.*}.mp4")
percent=$((100 - av1edFileSize * 100 / origFileSize))
percent=$( printf '%d' $percent )

result="File size reduced by "
result=$result$percent
result="$result percent"
echo $result
#------------------------------------------------------------------------------------------
