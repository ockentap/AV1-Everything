#!/bin/sh
###################################################################################################
#
# av1me_rec.sh - Shell Script to Recursively Encode Videos with AV1 Codec
#
# This script looks for encodable video files in a directory
# and uses the av1me.sh script to encoed them to AV1.
#
# Author: Dennis Rohner (@midzer)
# URL: https://github.com/midzer/av1me
#
# Author: Ockentap (@ockentap)
# URL:https://github.com/ockentap/AV1-Everything
#
# License: MIT
#
# Version 0.1
#
###################################################################################################

#Renames all directories and files with spaces in them, be careful as it will cause issues with existing filepaths.
find ./ -depth -name "* *" -execdir rename " " "_" "{}" ";"

# Enter "/location/of/the/" script
av1me="./av1me.sh"

# Define, which files are to be encoded
encodable="mp4|mkv|mov|MP4|MKV|MOV"

# Enter directory to start (recursively) looking for encodable files
dir="./"

find $dir -regextype posix-extended -regex ".*\.($encodable)" -exec sh -x $av1me {} \;

