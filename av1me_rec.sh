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

# Enter "/location/of/av1me" script
av1me="./av1me.sh"

# Define, which files are to be encoded (case sensitive)
# If all files in a directory will be video files with different extensions then use
# encodable="*" 
encodable="mp4|mkv|mov|MP4|MKV|MOV"

# Enter directory to start (recursively) looking for encodable files
dir="/location/of/files"

find $dir -regextype posix-extended -regex ".*\.($encodable)" -exec sh -x $av1me {} \;
