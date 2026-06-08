# Use Cases

`compressor.py` is useful anywhere you have a library of video files and want to save disk space without sacrificing too much quality.

---

## Personal media library

**Scenario:** You have a NAS or external drive with years of video files — recordings, downloaded content, family videos. Most are H.264, some are HEVC. Space is running low.

```bash
# Encode entire library
python3 compressor.py /mnt/nas/media --crf 28 --mode advanced

# Check what would be encoded before running
python3 compressor.py /mnt/nas/media --crf 28 --mode advanced --dry-run
```

**Expected savings:** H.264 → AV1 typically 60-70% size reduction. HEVC → AV1 typically 30-50%.

**Watch out for:** Short clips (<10s) can actually get larger with AV1 due to overhead. Use `--space-saver` to automatically skip those.

---

## Home security footage

**Scenario:** You have a CCTV system recording 24/7. The footage is H.264, 1080p, 8 hours per day = ~50GB/day. You want to keep 30 days but it's taking too much space.

```bash
# Encode with space-saver to avoid enlarging short clips
python3 compressor.py /srv/cctv/footage --crf 35 --space-saver --encoder libsvtav1

# Run as cron job at 3am when nobody's watching
0 3 * * * /usr/bin/python3 /home/media/AV1-Everything/compressor.py /srv/cctv/footage --crf 35 --space-saver --encoder libsvtav1 >> /var/log/compressor.log 2>&1
```

**Why AV1:** Better compression than H.265 for the same quality. 30 days of 1080p CCTV at CRF 35 ≈ 15GB with AV1 vs ~50GB H.264.

**Note:** CCTV footage is typically low-motion (fixed camera). AV1 compresses this extremely well — you may see 80%+ reduction.

---

## Photo/video management workflow (Immich, Jellyfin, Plex)

**Scenario:** You use Immich (or Jellyfin/Plex) to manage your media. Videos are uploaded from phones, encoded in various formats. You want to standardize to AV1 to save storage in your media server.

```bash
# Encode new uploads weekly (cron job)
0 4 * * 0 /usr/bin/python3 /home/media/AV1-Everything/compressor.py /path/to/immich/upload --crf 28 --space-saver --encoder libsvtav1

# Or encode everything once and be done
python3 compressor.py /path/to/immich/library --crf 25 --mode advanced
```

**Why in-place replacement:** Immich (and Jellyfin/Plex) identify files by path and filename. The atomic replace keeps the same path, so no database updates needed — the server just sees a new file with the same name.

**Watch out for:** If your media server is actively scanning a file while it's being encoded, you may get a read error. Run when server is idle or use `--dry-run` to pre-check.

---

## Archival / long-term storage

**Scenario:** You're archiving video projects, interviews, conference recordings. You want to keep them for 10+ years but storage costs matter.

```bash
# Archive quality: smaller file, slightly lower quality (acceptable for archived raw footage)
python3 compressor.py /mnt/archrive/project-2024 --crf 32 --mode advanced

# Or use space-saver to automatically pick the better result
python3 compressor.py /mnt/archrive/project-2024 --crf 30 --space-saver --mode advanced
```

**Why CRF 30-32:** Good balance between file size and quality for archival. For reference: CRF 23 = visually lossless (Netflix quality), CRF 28 = very good (YouTube quality), CRF 35 = acceptable (CCTV quality).

---

## Batch processing for content creators

**Scenario:** You record screen recordings, demos, tutorials. They go into a folder, you want to compress before uploading or sharing.

```bash
# After recording session — encode and move to upload folder
python3 compressor.py ~/recordings/draft --crf 26 --space-saver
# Then: rsync to cloud or upload to platform

# Continuous processing: new recordings land in /watch, encoded to /done
# Use inotifywait to trigger encode on new file
inotifywait -m /watch -e create -e moved_to |
  while read path action file; do
    [ "${file: -4}" == ".mp4" ] && python3 compressor.py "$path$file" --crf 28
  done
```

---

## Hardware-limited setups (NAS, single-board computers)

**Scenario:** You have a NAS (Synology, QNAP, TrueNAS) with limited CPU. SVT-AV1 is optimized for such environments — it scales from embedded to server-class.

```bash
# Low-power NAS (Jellyfin transcoding node)
python3 compressor.py /volume1/media --crf 33 --encoder libsvtav1 --mode basic
# Basic mode uses simpler settings, faster encode, acceptable quality

# Raspberry Pi 4 (4GB, arm64)
python3 compressor.py /mnt/storage/videos --crf 38 --encoder libsvtav1 --mode basic
# Higher CRF (worse quality) but achievable on Pi 4 in ~2x realtime
```

**SVT-AV1 performance:**
| Hardware | Mode | CRF 30 speed |
|----------|------|-------------|
| Desktop (Ryzen 9, 16 cores) | Advanced | ~10x realtime |
| Laptop (i7, 8 cores) | Advanced | ~4x realtime |
| NAS (ARM, 4 cores) | Basic | ~0.8x realtime |
| Raspberry Pi 4 | Basic | ~0.4x realtime |

---

## Automating with cron

```bash
# Every Sunday at 3am, encode any new files in the library
0 3 * * 0 cd /home/media && /usr/bin/python3 AV1-Everything/compressor.py /mnt/nas/media --crf 28 --encoder libsvtav1 >> /var/log/compressor.log 2>&1

# Every night at 2am, encode footage from previous day
0 2 * * * /usr/bin/python3 /home/media/AV1-Everything/compressor.py /srv/cctv/$(date -d yesterday +%Y-%m-%d) --crf 35 --space-saver
```

**Monitoring:** Check the JSON Lines log for results:
```bash
tail -f ~/.compressor.log | python3 -c "import sys,json; [print(json.loads(l).get('status'), json.loads(l).get('file','')) for l in sys.stdin]"
```

---

## Space-saver mode (avoid enlarging files)

AV1 has overhead on short clips. A 5-second clip might go from 1MB H.264 to 1.2MB AV1. `--space-saver` skips those automatically.

```bash
# Only keep AV1 if it's actually smaller
python3 compressor.py /path/to/videos --space-saver --crf 30

# Combine with dry-run to preview what would be accepted
python3 compressor.py /path/to/videos --space-saver --crf 30 --dry-run
```

---

## Encoding with hardware acceleration

If you have a modern GPU with Quick Sync (Intel), NVENC (NVIDIA), or VAAPI (Linux Intel/AMD):

```bash
# Intel Quick Sync (Linux)
python3 compressor.py /path/to/videos --hw-accel qsv --crf 28

# NVIDIA NVENC
python3 compressor.py /path/to/videos --hw-accel nvenc --crf 28

# macOS VideoToolbox
python3 compressor.py /path/to/videos --hw-accel videotoolbox --crf 28
```

**Note:** Hardware encoding of AV1 is available on newer GPUs (Intel gen 11+, NVIDIA RTX 30xx+, Apple Silicon). If unavailable, falls back to software (SVT-AV1 or libaom-av1).

---

## Troubleshooting

```bash
# Test FFmpeg is available
ffmpeg -version && ffprobe -version

# Dry-run to see what would be encoded without encoding
python3 compressor.py /path/to/videos --dry-run

# Show full help
python3 compressor.py --help

# Check what the script will do before running
# 1. List all video files
find /path/to/videos -type f \( -name "*.mp4" -o -name "*.mkv" -o -name "*.avi" \) | head
# 2. Check total size
du -sh /path/to/videos
# 3. Check available disk space (need ~2x largest file)
df -h /path/to/videos
```

---

## What NOT to use this for

- **Live streaming** — AV1 has high encode latency, not suitable for real-time
- **Very short clips (<5s)** — overhead may enlarge rather than compress
- **Already AV1 files** — script skips these (won't re-encode AV1 to AV1)
- **Audio-only files** — script skips non-video files
- **Real-time collaboration** — no multi-user support, lockfile blocks concurrent runs