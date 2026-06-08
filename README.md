# AV1-Everything

**AV1 video transcoding script — replaces your videos with space-saving AV1 encodes.**

## What it does

Recursively walks a directory, finds all video files (H.264, H.265/HEVC, VP9), encodes them to AV1 + Opus, and replaces the originals atomically. Output stays in the same subdirectory as the original.

## Quick start

```bash
# Encode everything in /path/to/videos with default settings (CRF 30, SVT-AV1)
python3 compressor.py /path/to/videos

# Higher quality (lower CRF), slower encode
python3 compressor.py /path/to/videos --crf 20 --mode advanced

# Space-saver: only accept output if it's smaller than the original
python3 compressor.py /path/to/videos --space-saver

# Use different encoder
python3 compressor.py /path/to/videos --encoder libaom-av1

# Headless (no TUI) — suitable for cron jobs
python3 /home/media/AV1-Everything/compressor.py /mnt/nas/videos --encoder libsvtav1 --crf 28 --mode advanced
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--crf N` | Quality (0=lossless, 63=worst) | 30 |
| `--encoder NAME` | `libsvtav1`, `libaom-av1`, `librav1e` | `libsvtav1` |
| `--mode basic\|advanced` | Basic = fast, Advanced = slower but better compression | `basic` |
| `--space-saver` | Only accept output if smaller than input | off |
| `--hw-accel NAME` | `vaapi`, `qsv`, `nvenc`, `videotoolbox` | auto-detect |
| `--dry-run` | Show what would be encoded without encoding | off |
| `--help` | Full help | — |

## Requirements

- Python 3.8+
- FFmpeg + ffprobe (installed and in PATH)
- Sufficient disk space: ~2× the size of the largest video file (temp space)

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Arch
sudo pacman -S ffmpeg

# macOS
brew install ffmpeg
```

## Architecture

```
Target directory
├── video1.mp4      (H.264, 50MB)
│   ├── renamed to  video1_to_be_encoded.mp4
│   ├── encoded to  .video1.mp4.temp/  (AV1, 8MB)
│   └── atomic move to video1.mp4 (AV1, 8MB)
├── video2.mkv      (HEVC, 120MB)
│   └── same process
└── subdir/
    └── video3.mp4  (VP9, 30MB)
        └── same process
```

Key behaviors:
- **Atomic writes** — temp file + `shutil.move()` so never corrupts originals
- **In-place replacement** — same directory, same filename, AV1 codec
- **Lockfile** — only one instance runs per output directory
- **Graceful failures** — corrupt videos skipped, not crashed
- **SIGINT propagation** — Ctrl+C kills ffmpeg child, not just Python

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (all files encoded) |
| 1 | Recoverable (some files skipped, errors logged) |
| 2 | Fatal (dependency missing, configuration error) |

## Output format

Each run outputs JSON Lines for machine parsing:

```
{"status": "encode_start", "file": "/path/video.mp4", "size": 52428800}
{"status": "encode_progress", "file": "/path/video.mp4", "percent": 45}
{"status": "encode_success", "file": "/path/video.mp4", "original_size": 52428800, "encoded_size": 8388608, "space_saved": 44040192}
{"status": "summary", "total": 3, "encoded": 2, "skipped": 1, "failed": 0, "space_saved": 88080384}
```

## Configuration

Config file at `~/.compressor.conf` (optional):

```json
{
  "crf": 28,
  "encoder": "libsvtav1",
  "mode": "advanced",
  "space_saver": true
}
```

CLI flags override config file values.

## Test suite

```bash
python3 test_runner.py
```

78 tests covering: file paths, encoding edge cases, cross-OS, hardware acceleration, signal handling, JSON output, curses UI, config handling, concurrency.

## History

This repo originally contained bash scripts (`av1me.sh`, `av1me_rec.sh`). They worked but had issues: shell injection vulnerabilities, no atomic writes, no dependency checking, no clean error handling, crashes on certain filenames.

`compressor.py` is a complete Python rewrite. See `CHANGELOG.md` for the full comparison.