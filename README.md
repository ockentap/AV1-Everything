# AV1-Everything

Encode any `ffmpeg supported` video in a folder to `AV1 codec` using ffmpeg.

## TODO

*Make the script rename files when a name conflict emerges, i.e. converting 1.mkv to 1.mp4 will overwrite any existing 1.mp4.

*Better way to rename moved source files with `Non-GNU mv`, currently it uses epoch time as the filename.

*Test the script more throughly for more defects.


## Configuration

In `av1me.sh` & `av1me_rec.sh` set your desired parameters.

## Requirements

Debian/Ubuntu

`ffmpeg & ffprobe`
`debian-devel`

Arch

`ffmpeg & ffprobe`
`base-devel`

## Usage

To process videos in a directory recursively, edit `dir` in `av1me_rec.sh` and run it.

For single files use `av1me.sh $FILENAME`.

## Tip
Run `detox` on folders to make the filenames POSIX compliant. 
https://github.com/dharple/detox

The script is able to rename files but the accuracy IRL hasn't been proven. 
