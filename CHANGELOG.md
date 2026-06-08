# Changelog: AV1-Everything Bash → Python

## Overview

`compressor.py` is a ground-up Python rewrite of the original bash scripts (`av1me.sh`, `av1me_rec.sh`). The intent and FFmpeg command structure are preserved, but the entire implementation is new — different language, different architecture, different failure modes.

---

## What's the same

- FFmpeg-based AV1 + Opus encoding
- Recursive directory walk
- Codec detection via ffprobe
- Skip AV1 source files (don't re-encode)
- CRF quality control
- Basic/advanced encoding modes

---

## What was fixed

| # | Bash bug | Python fix |
|---|----------|------------|
| 1 | `$(origFile)` undefined variable — syntax error on first file | Uses `pathlib.Path` objects, no shell interpolation |
| 2 | `continue` outside loop — crashes on first file | Proper Python loop/exception handling |
| 3 | Vendor stubs only — breaks on fresh clone | `pip install --target=vendor` with full dependencies |
| 4 | No dependency check — cryptic ffmpeg errors | `check_ffmpeg()` exits cleanly with install hint |
| 5 | Pipe deadlock — ffprobe stderr fills buffer | Async char-by-char reading with `select()` |
| 6 | Cross-device rename fails silently | `shutil.copy2 + os.unlink` fallback with EXDEV catch |
| 7 | Stats miscount — AV1 larger than input reported as "skipped" | `elif saved < 0` branch correctly classifies |
| 8 | Headless mode missing ffmpeg check | `check_ffmpeg()` called at start of `run_headless()` |
| 9 | `IMAGEIO_FFMPEG_NO_PREVENT_SIGINT` not set — SIGINT only kills Python, not ffmpeg child | Set on every subprocess call |
| 10 | No cleanup on interrupt — temp files orphaned | `try/finally` guarantees cleanup on success/error/signal/timeout |
| 11 | Output filename collision — same name different extension overwrites | Atomic commit with verification before any destructive op |
| 12 | `save_config()` had stray `end` keyword — Python syntax error | Removed, fixed config handling |

---

## What was added

| Feature | Bash | Python |
|---------|------|--------|
| Atomic writes | ❌ | ✓ temp file + `shutil.move` |
| Lockfile (no concurrent runs) | ❌ | ✓ `fcntl.flock` |
| Space-saver (reject AV1 if larger than input) | ❌ | ✓ `--space-saver` flag |
| Curses TUI with progress bar and spinner | ✓ | ✓ rewritten |
| Headless CLI mode | Via env var | ✓ first-class argparse CLI |
| Hardware acceleration probe | Manual | ✓ `probe_hw_accels()` with VAAPI/QSV/NVENC |
| Config file (`~/.compressor.conf`) | ❌ | ✓ with JSON persistence |
| JSON Lines logging | ❌ | ✓ `json_log()` for machine parsing |
| Deterministic exit codes (0/1/2) | ❌ | ✓ `EXIT_SUCCESS/RECOVERABLE/FATAL` |
| Disk space check before encode | ❌ | ✓ `os.statvfs()` |
| Skip OS metadata files (`.DS_Store`, `Thumbs.db`, etc.) | ❌ | ✓ `SKIP_FILES` set |
| FFmpeg timeout (2hr max per file) | ❌ | ✓ `process.wait(timeout=7200)` |
| Zero-byte file handling | ❌ | ✓ skip with guard |
| Corrupt video handling | Crashes | ✓ graceful exit |
| Multi-dot/unicode/hidden filenames | Risky | ✓ thorough `is_video_file()` |
| Test suite (78 tests) | ❌ | ✓ `test_runner.py` |
| FFmpeg dependency validation (headless mode) | ❌ | ✓ `check_ffmpeg()` in both modes |
| Cross-device fallback | ❌ | ✓ `EXDEV` handling |

---

## Architectural differences

| Aspect | Bash | Python |
|--------|------|--------|
| File discovery | `find` + shell glob | `pathlib.Path.rglob()` |
| Codec detection | `ffprobe` + `grep` | `json.load()` from ffprobe JSON output |
| Encoding loop | `while read` + `case` | `for` loop over `list[Path]` |
| Error handling | `set -e` (crash on any error) | `try/except` per operation |
| Temp file management | `mv` + manual cleanup | `tempfile` + `finally` block |
| CLI interface | Env vars + positional args | `argparse` with named flags |
| State persistence | Config file only | `json.dump()` to `~/.compressor.conf` |
| Logging | Plain text to file | JSON Lines (`{"status": "...", ...}`) |

---

## Classification

**Is this a fork?** No. This is a new project that solved the same problem from scratch.

The bash scripts were written by the same author (ockentap). The Python rewrite has no shared git history with the bash version — no commits in common, no diff relationship. It's a ground-up rebuild of the author's own work.

Think of it as: the author wrote version 1 in bash, then wrote version 2 in Python. Same author, same intent, no upstream dependency.