# av1me

Encode any `ffmpeg supported` video in a folder to `mp4` AV1 using ffmpeg.

## Configuration

In `av1me.sh` set your desired `quality`.
## Requierments

Debian/Ubuntu

`ffmpeg`
`debian-devel`

Arch

`ffmpeg`
`base-devel`

## Usage

To process videos in a directory recursively, edit `dir` in `av1me_rec.sh` and run it.

For single files use `av1me.sh $FILENAME`.

## Tip
Run `detox` on folders to make the filenames POSIX compliant. 
https://github.com/dharple/detox
