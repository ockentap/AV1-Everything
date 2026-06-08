# Test Checklist for compressor.py (Video Transcoding Focus)

## File Path Issues

| # | Test | Expected behavior | Common failure |
|---|------|------------------|----------------|
| 1 | Path with spaces | Encodes correctly | Fails if unquoted in subprocess |
| 2 | Unicode filenames | Works on all OS | Fails on Windows with locale |
| 3 | Relative paths | Resolves correctly | Path not found if cwd changes |
| 4 | Absolute paths | Works | Symlink loops on some systems |
| 5 | Network paths (smb://) | Fails gracefully | Timeout or hangs |
| 6 | Long paths (>260 chars, Windows) | Fails with clear error | Silent truncation on older Windows |
| 7 | Read-only files | Skipped with warning | Permission denied crash |
| 8 | File disappears mid-encoding | Cleanup + skip | Orphan temp files left behind |
| 9 | Input file deleted before encoding | Skip + log | Crash |
| 10 | Output disk full mid-encoding | Temp file cleaned, error logged | Temp files orphaned |
| 11 | `.DS_Store`, `Thumbs.db`, desktop.ini | Auto-skipped | Processed as video → crash |
| 12 | Case collisions (File.txt vs file.txt) | Only one processed on Windows | Duplicate encoding or overwrite |
| 13 | No extension (`/data/myvideo`) | Processed correctly | Extension check fails |
| 14 | Leading dot (hidden file) | Processed | Skipped by dotfile filter |
| 15 | Multiple dots in name (`file...mp4`) | Processed correctly | Extension parsing breaks |
| 16 | Circular symlink chain | Detected, skipped | Infinite loop |
| 17 | Dangling symlink | Fails gracefully | Crash or hang |
| 18 | Windows reserved names (CON, NUL, AUX) | Skipped with warning | Filesystem error |

## Encoding / FFmpeg Issues

| # | Test | Expected behavior | Common failure |
|---|------|------------------|----------------|
| 19 | CRF 20 vs source same codec | Skip or minimal savings | Wrong skip logic |
| 20 | CRF 50 (lowest quality) | Smallest file | Blocky artifacts |
| 21 | Already AV1 → AV1 | Skips correctly | False positive |
| 22 | HEVC → AV1 | Converts | Wrong skip check |
| 23 | VP9 → AV1 | Converts | encode_hevc check too narrow |
| 24 | Corrupt video file | Fails gracefully | ffmpeg hangs or crashes |
| 25 | Zero-length / 0-byte file | Skipped | Division by zero |
| 26 | Audio-only file (no video stream) | Skipped | get_video_duration returns None |
| 27 | Multiple video streams | Uses first video stream | Wrong stream selected |
| 28 | Subtitle tracks in MKV | Copied correctly | -c:s copy missing |
| 29 | HDR content | Tone-mapped or skipped | Wrong colorspace output |
| 30 | 10-bit video | Encodes as 10-bit | Player compatibility issues |
| 31 | Framerate 23.976 fps | Duration accurate | Integer overflow on time_ms |
| 32 | Very long video (>4hrs) | Progress % correct | Same overflow risk |
| 33 | libsvtav1 not installed | Clear error | "encoder not found" cryptic |
| 34 | libx265 not installed | Clear error | Same |
| 35 | libopus not installed | Falls back to aac or fails gracefully | Silent broken audio |
| 36 | Encoder crashes mid-job | Temp cleaned, next file continues | Stuck or crashed |
| 37 | Invalid CRF for encoder | Error logged clearly | Unclear message |
| 38 | -b:v 0 with CRF + non-CRF encoder | Works for AV1 | Fails silently for H.264 |
| 39 | Named pipe / FIFO passed as input | Skipped | ffprobe hangs |
| 40 | Device file (/dev/urandom) passed | Skipped | Crash or infinite read |

## Cross-OS Issues

| # | Test | Linux | macOS | Windows |
|---|------|-------|-------|---------|
| 41 | ffmpeg/ffprobe in PATH | ✓ | Needs install | Needs install |
| 42 | pathlib.Path used throughout | ✓ | ✓ | ✓ |
| 43 | curses library | ✓ | ✓ | ✓ |
| 44 | Temp file location | /tmp | /var/folders | %TEMP% |
| 45 | os.rename atomic on overwrite | ✓ | ✓ | ❌ (Windows) |
| 46 | signal.SIGUSR1 | ✓ | ✓ | ❌ (not available) |
| 47 | os.R_OK\|os.W_OK | ✓ | ✓ | Admin issues |
| 48 | UTF-8 encoding explicit | ✓ | ✓ | ✓ |
| 49 | os.statvfs / shutil.disk_space | Works | Works | Works |
| 50 | Mixed path separators on Windows (C:/Users\file) | Handled correctly | N/A | Treated as single path |
| 51 | Cross-device temp+output (mv fails) | Falls back to copy+delete | Same | Same |

## Hardware Acceleration

| # | Test | Expected | Failure mode |
|---|------|----------|--------------|
| 52 | VAAPI on Linux Intel/AMD | Works if /dev/dri/ | Silent fallback to software |
| 53 | QSV on Linux | Works if libmfx | "hwaccel not found" |
| 54 | NVENC on Linux NVIDIA | Works if driver | Silent fallback |
| 55 | No GPU available | Software encoding | Should probe and default |
| 56 | -hwaccel + hardware encode | Both flags work | Redundant causes error |
| 57 | Invalid hwaccel for encoder | Clear error | Silently ignores |

## Curses UI Issues

| # | Test | Expected | Failure |
|---|------|----------|---------|
| 58 | Terminal <80x24 | Wraps/scrolls | Output garbled |
| 59 | No $TERM set | Falls back | Crash or garbled |
| 60 | Non-UTF8 terminal | ASCII fallback | Unicode errors |
| 61 | Arrow keys not detected | Vi keys fallback | Arrow keys fail |
| 62 | Enter key \r vs \n | Both handled | Enter not recognized |
| 63 | Terminal resize during menu | Handled | Crash or partial render |
| 64 | curses import fails | Falls back to headless/cli | Crash |

## Config / Persistence

| # | Test | Expected | Failure |
|---|------|----------|---------|
| 65 | Corrupted JSON config | Defaults loaded, warning shown | Crash on json.load |
| 66 | Config permission denied | Warning, uses defaults | Silent failure |
| 67 | Config written to read-only location | Fails gracefully | Crash |
| 68 | Config has unknown keys | Ignored | Overwrites known keys |
| 69 | Config written while reading | Read wins or retry | Partial/corrupt read |

## Signal / Interrupt Handling

| # | Test | Expected | Failure |
|---|------|----------|---------|
| 70 | Ctrl+C during encoding | Graceful cleanup, temp files removed | Orphaned temp files |
| 71 | Ctrl+C during ffprobe | Same | Temp rename not reverted |
| 72 | SIGTERM (system shutdown) | Same | Orphaned files |
| 73 | Script killed mid-rename | _to_be_encoded suffix stuck | Name corruption |
| 74 | Ctrl+C before any file | Exit cleanly | Crash |
| 75 | Double Ctrl+C | Force exit | Blocked in cleanup |

## Progress / Logging

| # | Test | Expected | Failure |
|---|------|----------|---------|
| 76 | out_time_ms missing from ffmpeg | Progress stalls | int() crash on ValueError |
| 77 | Log file write fails (disk full) | Console still works | Crash |
| 78 | \r progress on non-TTY (cron) | Newlines instead | Invisible overwrite |

## Size / Edge Cases

| # | Test | Expected | Failure |
|---|------|----------|---------|
| 79 | File exactly MIN_FILE_SIZE (1MB) | Processed | Borderline skip |
| 80 | Very large file (100GB) | Works | Temp disk space exhausted |
| 81 | Many files (10,000+) | All processed | Memory growth |
| 82 | Deeply nested dirs (50+ levels) | Walk succeeds | Path length limits |
| 83 | FIFO / socket files | Skipped | ffprobe hangs |

## Structured Output (Agent Contract)

| # | Requirement | Status |
|---|-------------|--------|
| 84 | Never plain string errors — JSON: `{"status": "error", "error_type": "...", "message": "...", "recoverable": bool}` | ☐ |
| 85 | Success: `{"status": "success", "file": "...", "original_size": N, "encoded_size": N, "space_saved": N}` | ☐ |
| 86 | JSON log lines via json.dumps() for machine readability | ☐ |
| 87 | Exit codes: 0=success, 1=recoverable, 2=fatal | ☐ |
| 88 | Every subprocess wrapped: stderr captured, return code checked | ☐ |
| 89 | ffmpeg/ffprobe checked with `shutil.which` before any operation | ☐ |
| 90 | Atomic writes: temp file then shutil.move(), never direct to final path | ☐ |
| 91 | OS metadata files (.DS_Store, Thumbs.db, desktop.ini, ._*) auto-skipped | ☐ |

## Cross-OS Defensive Patterns

| # | Requirement | Status |
|---|-------------|--------|
| 92 | `shutil.which` for ffmpeg/ffprobe discovery (cross-platform) | ☐ |
| 93 | `shutil.move` / `shutil.copy` instead of `os.rename` where atomicity matters | ☐ |
| 94 | `os.stat()` instead of `stat -c` subprocess | ☐ |
| 95 | `tempfile.gettempdir()` for cross-platform temp location | ☐ |
| 96 | No hardcoded `/tmp` paths | ☐ |
| 97 | SIGUSR1 wrapped in try/except AttributeError | ☐ |
| 98 | curses wrapped in try/except; fallback to cli mode | ☐ |

## Agent Integration

| # | Test | Expected | Failure |
|---|------|----------|---------|
| 99 | No stdin blocking if not expected | Returns immediately | Hangs waiting |
| 100 | --help works and documents all args | Shows usage | Missing docs |
| 101 | Unknown args: error with clear message | Rejects gracefully | Silently ignored |
| 102 | Verbose/quiet mode switchable | No TTY = no ANSI/spinners | Spinners in logs |
| 103 | Two parallel runs same output path | Race condition handled | Overwrite/corruption |
| 104 | Re-run after failure leaves clean state | No corrupted temp files | Partial state left |
| 105 | JSON output is single-line parseable | Valid JSON each line | Multi-line splitted |

## Smoke Tests (Priority Order)

1. Basic encode — H.264 MP4 → AV1 MP4, CRF 30
2. Spaces in filename
3. Ctrl+C during encode — verify temp files cleaned
4. Already AV1 file — should skip
5. No ffmpeg installed — clear error message
6. Read-only input file — skipped with warning
7. Output to full disk — graceful failure
8. Config file corrupted — uses defaults, no crash
9. Very short video (<1MB) — skipped or processed correctly
10. Unicode filename — works on Linux

---

## Top Priority Fixes

1. **H15/89** — Check ffmpeg/ffprobe with `shutil.which` before anything else; clear error if missing
2. **H18/84** — JSON schema output for all errors and successes
3. **H1** — Consistent `pathlib.Path` everywhere; no mixed `os.path.*` and string ops
4. **H11/70-75** — Audit every exit path; temp files in `finally` blocks; rename reverted on interrupt
5. **H8/25** — Zero-byte guard: `if size == 0` skip before any division or ffmpeg call
6. **H7/91** — Skip `.DS_Store`, `Thumbs.db`, `desktop.ini`, `._*` files in file scan
7. **H16** — Check disk space before encoding starts
8. **H20/86** — JSON log lines for machine-readable output
9. **H21/87** — Exit codes: 0/1/2 deterministic
10. **H24/90** — Atomic writes: temp file → shutil.move()

---

## Regression Table (fill in as bugs are found)

| # | Description | Input that triggered | Expected | Fixed in |
|---|-------------|---------------------|----------|----------|
| 1 | Shell script `$(origFile)` syntax error | Any file | Move succeeds | PR #4 |
| 2 | Shell script `continue` outside loop | Any file | No error | PR #4 |
| 3 | Vendor directory stubs only | Fresh clone | Script works standalone | PR #4 |
| 4 | Stray `end` keyword (Python syntax error) | `save_config()` called | Script imports cleanly | compressor.py (hardened) |
| 5 | Pipe buffer deadlock — synchronous `readline()` on ffmpeg stdout | Large stderr output | Async char-by-char read | compressor.py (hardened) |
| 6 | Destructive `os.remove(final_path)` before verifying temp output | Encoding fails mid-way | Verify before any destructive op | compressor.py (hardened) |
| 7 | Mixed `os.path.*` and `pathlib.Path` throughout | Windows path with spaces | Consistent pathlib everywhere | compressor.py (hardened) |
| 8 | No ffmpeg/ffprobe availability check | Missing ffmpeg | Clear error with install hint | compressor.py (hardened) |
| 9 | Zero-byte file — division by zero in progress calc | 0-byte video | Skip before encoding | compressor.py (hardened) |
| 10 | `.DS_Store`, `Thumbs.db`, `desktop.ini` processed as video | OS metadata in scan | Auto-skipped | compressor.py (hardened) |
| 11 | Curses `addstr` crashes on small terminal (<80x24) | Resize during menu | `try/except curses.error` | compressor.py (hardened) |
| 12 | `IMAGEIO_FFMPEG_NO_PREVENT_SIGINT` not set — SIGINT only kills Python, not ffmpeg child | Ctrl+C during encode | SIGINT propagates to ffmpeg | compressor.py (hardened) |

---

## Agentic Debugging & Evaluation Frameworks

These reference repositories define how to test agent tool-calling behavior. Use them to validate the script's interface when called by an autonomous agent.

### Tool Correctness & Argument Validation
| # | Test | Expected | Reference |
|---|------|----------|-----------|
| 106 | Agent passes file_path with spaces — script handles without shell injection | No crashes, correct output | confident-ai/deepeval (Tool Correctness metric — evaluates whether agent passes correctly formatted paths/params to scripts) |
| 107 | Agent passes wrong type (int instead of str) — script rejects cleanly | TypeError or ValueError, not AttributeError | Giskard-AI/giskard-oss (scenario API — tests dynamic multi-turn agent behavior) |
| 108 | Agent passes non-existent path — script returns structured error JSON | `{"status": "error", "error_type": "FileNotFoundError", ...}` | brunoborges/jdb-debugger-skill (pipeline pattern: parallel dispatch + file-based reporting) |
| 109 | Agent calls script twice with same input — second run skips (idempotent) | Same result, no corruption | DrDroidLab/sample-debug-agent (idempotent runbook pattern) |
| 110 | Agent passes path with unicode — script handles without UnicodeDecodeError | Clean encode, no crashes | All frameworks |

### Multi-Turn Agent Pipeline Testing
| # | Test | Expected | Reference |
|---|------|----------|-----------|
| 111 | Agent calls script → gets error → fixes path → retries → succeeds | State preserved correctly between calls | Giskard-AI/giskard-oss (Scenario API for multi-turn conversations — supports Groundedness, Conformity, LLMJudge checks) |
| 112 | Agent calls script while previous run still encoding (Ctrl+C then new run) | Previous temp files cleaned, no collision | Agent-Pattern-Labs/state-trace (bounded working-memory, handles stale state cleanup) |
| 113 | Agent runs script 100 times sequentially — no memory leak | Memory stable, no growth | state-trace (bounded memory with decay/compression/lifecycle retention) |

### Regression & Snapshot Testing
| # | Test | Expected | Reference |
|---|------|----------|-----------|
| 114 | Script output format unchanged after refactor — JSON schema stable | All existing fields present, same types | confident-ai/deepeval (CI/CD integration, catches breaking changes) |
| 115 | Forbidden tool mutations logged — script doesn't silently skip files | Every skip is logged with reason | DrDroidLab/sample-debug-agent (runbook execution logs — every action traced) |
| 116 | Cassettes of live tool calls recorded — reproduce failures | Can replay any run | Agent-Pattern-Labs/state-trace (trajectory-informed retrieval, replay capability) |
| 117 | Breaking change to output format caught by automated test | CI fails, human reviews | danielrosehill/Awesome-AI-Evaluations-Tools (aggregates 500+ eval frameworks) |

### Deterministic Execution
| # | Test | Expected | Reference |
|---|------|----------|-----------|
| 118 | Same input file run twice — identical output size (within tolerance) | Deterministic within 1% | Agent-Pattern-Labs/state-trace (verified 35% solve-rate on SWE-bench) |
| 119 | Run with same input, different timestamps — output identical | Timestamps not embedded in output | imageio-ffmpeg (binary pipes, no text encoding variability) |
| 120 | Script called from different cwd — produces same output path | Relative paths resolved correctly | All frameworks |

---

## FFmpeg & Media Processing References

These upstream resources define how production FFmpeg wrappers handle edge cases.

### FFmpeg FATE (Automated Testing Environment)
| # | Test | Expected | Reference |
|---|------|----------|-----------|
| 121 | Zero-duration video file | Skipped with error logged | FFmpeg/FFmpeg/tests/fate (comprehensive test suite: audio codecs, video encoders, demuxers, filters — `make fate` runs 1000+ test cases) |
| 122 | Multi-stream video (video + audio + subtitle) | All streams handled, no crash | FFmpeg/FFmpeg/tests/fate (tests cover mov demuxer, matroska, MP4, subtitle streams, ATRAC3 audio) |
| 123 | Missing video packet drops | Clean failure, no hang | FFmpeg/FFmpeg/tests/fate (CRC/framecrc/md5/framemd5 test harness — detects corruption) |
| 124 | Malformed header | ffprobe returns empty, script skips | FFmpeg/FFmpeg/tests/fate (demuxer tests validate header parsing before stream decode) |
| 125 | Non-zero exit codes from ffprobe — caught and handled | Error logged, file skipped | FFmpeg/FFmpeg/tests/fate (non-zero exit codes fail the test harness) |

### Safe Subprocess Patterns (imageio-ffmpeg)
| # | Test | Expected | Reference |
|---|------|----------|-----------|
| 126 | FFmpeg produces massive stderr output — pipe doesn't deadlock | Async read, process completes | imageio-ffmpeg (binary pipe pattern — frames communicated over pipes without text decoding) |
| 127 | FFmpeg hangs — timeout kills it after X seconds | Process killed, temp cleaned | imageio-ffmpeg (uses `IMAGEIO_FFMPEG_NO_PREVENT_SIGINT=1` for proper SIGINT propagation to ffmpeg child) |
| 128 | FFmpeg interrupted (SIGINT) — propagation to child process | FFmpeg dies cleanly | imageio-ffmpeg (critical: `IMAGEIO_FFMPEG_NO_PREVENT_SIGINT` env var ensures Ctrl+C kills ffmpeg, not just Python parent) |
| 129 | FFmpeg produces binary output on stdout — no text decode error | Binary mode handled | imageio-ffmpeg (read_frames/write_frames use raw binary pipes, not text) |

### Cap-go FFmpeg Test Fixture Strategy
| # | Test | Expected | Reference |
|---|------|----------|-----------|
| 130 | Argument passing — special chars in paths don't break arg parsing | Encode succeeds | Cap-go/capacitor-ffmpeg (JS/native arg handling — fixture strategy: prefer generated synthetic fixtures, keep checked-in samples small, assert metadata not exact bytes) |
| 131 | Cancellation — script stops mid-encode, temp removed | Clean state | Cap-go/capacitor-ffmpeg (progress + cancellation testing — "assert metadata, stream layout, duration tolerances, and error handling before asserting exact bytes") |
| 132 | Metadata assertion — output file has video+audio streams after encode | Both streams present | Cap-go/capacitor-ffmpeg (plugin API boundary validation — small synthetic H.264+AAC MP4 for reencodeVideo() path) |

---

## Complete Test Run Order

### Phase 1 — Syntax & Import (always first)
1. Script imports without SyntaxError
2. All functions present (no missing definitions)
3. `shutil.which('ffmpeg')` check works

### Phase 2 — Smoke Tests (must pass before anything else)
4. Basic encode H.264 → AV1
5. Already AV1 file skipped
6. No ffmpeg installed → clear error
7. Zero-byte file → skipped

### Phase 3 — Path Edge Cases
8. Spaces in filename
9. Unicode (Cyrillic, Arabic, CJK)
10. Windows reserved names
11. Deeply nested paths (50+ levels)
12. Circular symlink chain

### Phase 4 — Encoding Edge Cases
13. Corrupt video → graceful failure
14. Audio-only file → skipped
15. Multiple video streams → uses first
16. HDR content → encoded or skipped
17. Very long video (>4hrs) → progress correct

### Phase 5 — Interrupt & Signal
18. Ctrl+C during encoding → temp cleaned
19. Ctrl+C before any file → exit clean
20. SIGTERM → same

### Phase 6 — Agent Contract
21. JSON schema output on success
22. JSON schema output on error
23. Exit codes deterministic (0/1/2)
24. Re-run after failure → clean state

### Phase 7 — Performance & Scale
25. 10,000 files — no memory growth
26. 100GB file — temp space managed
27. Cross-device temp+output → fallback works

---

*Last updated: 2026-06-08 — after Gemini hardening review + agent framework additions*
