import os
import subprocess
import tempfile
import shutil
import time
import sys
import signal
import json as _json
import shutil as _shutil
from datetime import datetime
from pathlib import Path
import threading
import errno
import argparse
import fcntl
import struct

# ── Curses (optional, try to import) ──────────────────────────────────────────
try:
    import curses
    _curses_imported = True
except ImportError:
    curses = None
    _curses_imported = False

# ── Constants ────────────────────────────────────────────────────────────────
VIDEO_EXTENSIONS = [
    'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', 'mpeg',
    'mpg', 'm4v', '3gp', 'ogv', 'ts', 'vob', 'mts', 'm2ts',
    'divx', 'xvid', 'rm', 'rmvb'
]
MIN_FILE_SIZE = 1 * 1024 * 1024
SKIP_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini', '._.DS_Store', '.AppleDouble', '.LSOverride'}
CONFIG_FILE = "video_converter_config.json"
FFMPEG_TIMEOUT_SEC = 7200  # 2h max per file

# Exit codes (agent contract)
EXIT_SUCCESS = 0
EXIT_RECOVERABLE = 1
EXIT_FATAL = 2

# ── Global state ─────────────────────────────────────────────────────────────
settings = {}
HW_ACCELS = []
current_process = {}

# Hardware acceleration descriptions
HW_ACCEL_INFO = {
    'vdpau': "VDPAU: NVIDIA-specific, decoding-focused, limited encoding support.",
    'cuda': "CUDA: NVIDIA GPU acceleration, good for NVENC encoding (H.264/H.265).",
    'vaapi': "VAAPI: Broad Linux support (Intel/AMD), efficient for H.264/VP9.",
    'qsv': "QSV: Intel Quick Sync, optimized for H.264/H.265 on Intel GPUs.",
    'drm': "DRM: Linux GPU interface, used with VAAPI, not standalone.",
    'opencl': "OpenCL: Cross-platform for filters, not primary encoding.",
    'vulkan': "Vulkan: Modern API, supports H.264/VP9, less common."
}
RECOMMENDED_HW_ACCELS = ['qsv', 'vaapi', 'cuda']

VIDEO_ENCODERS = {
    'qsv': ['h264_qsv', 'hevc_qsv', 'vp9_qsv'],
    'vaapi': ['h264_vaapi', 'vp9_vaapi', 'hevc_vaapi'],
    'cuda': ['h264_nvenc', 'hevc_nvenc'],
    'software': ['libx264', 'libx265', 'libvpx-vp9', 'libsvtav1']
}
AUDIO_ENCODERS = ['libopus', 'aac', 'libvorbis', 'libmp3lame']
CRF_OPTIONS = ['20', '25', '30', '35', '40', '45', '50']
VIDEO_BITRATES = ['0', '500k', '1000k', '2000k', '3000k']
AUDIO_BITRATES = ['64k', '96k', '128k', '192k', '256k']

VIDEO_ENCODER_CODEC_MAP = {
    'h264_qsv': 'h264', 'hevc_qsv': 'hevc', 'vp9_qsv': 'vp9',
    'h264_vaapi': 'h264', 'vp9_vaapi': 'vp9', 'hevc_vaapi': 'hevc',
    'h264_nvenc': 'h264', 'hevc_nvenc': 'hevc',
    'libx264': 'h264', 'libx265': 'hevc', 'libvpx-vp9': 'vp9', 'libsvtav1': 'av1'
}
AUDIO_ENCODER_CODEC_MAP = {
    'libopus': 'opus', 'aac': 'aac', 'libvorbis': 'vorbis', 'libmp3lame': 'mp3'
}

# ── CLI Argument Parser ─────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        prog="compressor.py",
        description="AV1 video transcoder with hardware acceleration support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compressor.py /path/to/videos
  python compressor.py /path/to/videos --crf 25 --encoder libx265
  python compressor.py /path/to/videos --hw-accel vaapi --mode advanced
  python compressor.py --help

Exit codes:
  0  Success (all files processed)
  1  Recoverable error (some files failed, retry may help)
  2  Fatal error (missing dependencies, bad arguments)
        """
    )
    parser.add_argument('directory', nargs='?', help='Target directory to scan for video files')
    parser.add_argument('--crf', default='30', choices=CRF_OPTIONS,
                        help='Constant Rate Factor quality (lower = better, default: 30)')
    parser.add_argument('--encoder', default=None,
                        help=f"Video encoder. Options: {', '.join(sum(VIDEO_ENCODERS.values(), []))}")
    parser.add_argument('--hw-accel', default=None,
                        help=f"Hardware acceleration. Options: {', '.join(HW_ACCEL_INFO.keys())}")
    parser.add_argument('--audio-encoder', default=None,
                        dest='audio_encoder', choices=AUDIO_ENCODERS,
                        help=f"Audio encoder. Options: {', '.join(AUDIO_ENCODERS)}")
    parser.add_argument('--audio-bitrate', default=None, dest='audio_bitrate',
                        choices=AUDIO_BITRATES, help=f"Audio bitrate. Options: {', '.join(AUDIO_BITRATES)}")
    parser.add_argument('--mode', default=None, choices=['basic', 'advanced'],
                        help='Output verbosity: basic (human) or advanced (verbose)')
    parser.add_argument('--encode-hevc', action='store_true', dest='encode_hevc',
                        help='Encode HEVC files (default: skip them)')
    parser.add_argument('--dry-run', action='store_true', dest='dry_run',
                        help='Scan directory and report what would be converted, without encoding')
    parser.add_argument('--space-saver', action='store_true', dest='space_saver',
                        help='Only accept compression if output is smaller than input. '
                             'Discard output and keep original if output would be larger.')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')
    return parser.parse_args()

# ── JSON Output Helpers (Agent Contract) ──────────────────────────────────────
def json_out(status, **kwargs):
    """Emit a single-line JSON object to stdout — machine-readable."""
    obj = {"status": status, "timestamp": datetime.now().isoformat(), **kwargs}
    print(_json.dumps(obj, ensure_ascii=False))

def json_log(event, **kwargs):
    """Emit a single-line JSON log line to the log file — machine-readable."""
    obj = {"event": event, "timestamp": datetime.now().isoformat(), **kwargs}
    # Write as single line to file
    try:
        with open(f"conversion_log_{datetime.now().strftime('%Y-%m-%d')}.jsonl", "a", encoding='utf-8') as f:
            f.write(_json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Never crash on logging failures
    # Also emit to human log for development
    if settings.get('mode') == 'advanced':
        print(f"[{event}] {kwargs}")

def json_error(error_type, message, recoverable=True, **kwargs):
    """Emit a structured error response — agent contract."""
    obj = {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "recoverable": recoverable,
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }
    print(_json.dumps(obj, ensure_ascii=False), file=sys.stderr)
    json_log("error", error_type=error_type, message=message, recoverable=recoverable, **kwargs)

def json_success(file_path, original_size, encoded_size, space_saved, **kwargs):
    """Emit a structured success response — agent contract."""
    obj = {
        "status": "success",
        "file": str(file_path),
        "original_size": original_size,
        "encoded_size": encoded_size,
        "space_saved": space_saved,
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }
    print(_json.dumps(obj, ensure_ascii=False))

# ── FFmpeg Availability Check ─────────────────────────────────────────────────
def check_ffmpeg():
    """Verify ffmpeg and ffprobe are available in PATH. Exit with JSON on failure."""
    for binary in ['ffmpeg', 'ffprobe']:
        if not _shutil.which(binary):
            json_error(
                "DependencyMissing",
                f"'{binary}' not found in PATH. Install ffmpeg first.",
                recoverable=False,
                install_hints={
                    "debian": "sudo apt install ffmpeg",
                    "arch": "sudo pacman -S ffmpeg",
                    "fedora": "sudo dnf install ffmpeg",
                    "macos": "brew install ffmpeg",
                    "windows": "winget install ffmpeg"
                }
            )
            sys.exit(EXIT_FATAL)
    json_log("ffmpeg_check", found=["ffmpeg", "ffprobe"])

# ── Hardware Probe ─────────────────────────────────────────────────────────────
def probe_hw_accels():
    global HW_ACCELS
    try:
        result = subprocess.run(
            ['ffmpeg', '-hwaccels'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding='utf-8', errors='replace'
        )
        lines = result.stdout.strip().split('\n')[1:]
        HW_ACCELS = [line.strip() for line in lines if line.strip()]
        json_log("hw_accel_probe", available=HW_ACCELS)

        # Only auto-select encoder if not explicitly overridden via CLI
        if not settings.get('_encoder_overridden'):
            for accel in ['qsv', 'vaapi', 'cuda']:
                if accel in HW_ACCELS:
                    settings['hw_accel'] = accel
                    settings['video_encoder'] = VIDEO_ENCODERS.get(accel, ['libx264'])[0]
                    json_log("hw_accel_selected", accel=accel, encoder=settings['video_encoder'])
                    break
            if not settings.get('hw_accel'):
                settings['hw_accel'] = 'software'
                settings['video_encoder'] = 'libx264'
                json_log("hw_accel_fallback", reason="no_gpu_found", encoder='libx264')
        else:
            json_log("encoder_cli_override", encoder=settings['video_encoder'], hw_accel=settings.get('hw_accel'))
    except Exception as e:
        json_log("hw_accel_probe_error", error=str(e))
        HW_ACCELS = []
        settings['hw_accel'] = 'software'

# ── Config Persistence ─────────────────────────────────────────────────────────
def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            _json.dump(settings, f, indent=4)
        json_log("config_saved", file=CONFIG_FILE)
    except Exception as e:
        json_log("config_save_error", error=str(e))

def load_config():
    config_path = Path(CONFIG_FILE)
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded = _json.load(f)
            settings.update(loaded)
            json_log("config_loaded", file=CONFIG_FILE)
        except (_json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            json_log("config_load_error", error=str(e), recoverable=True)

# ── Signal Handling ───────────────────────────────────────────────────────────
def signal_handler(sig, frame):
    json_log("signal_received", signal=sig)
    proc = current_process.get('process')
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    clean_up_current_file()
    json_log("signal_cleanup_complete", signal=sig, exit_code=EXIT_RECOVERABLE)
    sys.exit(EXIT_RECOVERABLE)

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGUSR1, signal_handler)
except AttributeError:
    pass  # Windows

# ── Cleanup (Guaranteed via finally) ─────────────────────────────────────────
def clean_up_current_file():
    """Guaranteed cleanup — called from finally blocks and signal handler."""
    renamed = current_process.get('renamed_file')
    original = current_process.get('original_file')
    if renamed and original:
        try:
            if Path(renamed).exists():
                json_log("cleanup_revert", from_=renamed, to_=original)
                Path(renamed).rename(original)
        except OSError as e:
            json_log("cleanup_revert_error", path=renamed, error=str(e))
    temp = current_process.get('temp_encoded_file')
    if temp:
        try:
            if Path(temp).exists():
                json_log("cleanup_temp_delete", path=temp)
                Path(temp).unlink()
        except OSError as e:
            json_log("cleanup_temp_error", path=temp, error=str(e))
    current_process.clear()

# ── FFprobe Wrappers ───────────────────────────────────────────────────────────
def run_ffprobe(file_path, stream_type):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', stream_type,
             '-show_entries', 'stream=index', '-of', 'csv=p=0', str(file_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding='utf-8', errors='replace', timeout=30
        )
        return [int(idx) for idx in result.stdout.strip().split('\n') if idx.strip().isdigit()]
    except subprocess.TimeoutExpired:
        json_log("ffprobe_timeout", file=str(file_path), stream=stream_type)
        return []
    except Exception as e:
        json_log("ffprobe_error", file=str(file_path), stream=stream_type, error=str(e))
        return []

def get_video_duration(file_path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding='utf-8', errors='replace', timeout=30
        )
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        return None
    except Exception as e:
        json_log("duration_error", file=str(file_path), error=str(e))
        return None

def get_codec_name(file_path, stream_specifier):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', stream_specifier,
             '-show_entries', 'stream=codec_name', '-of', 'default=nw=1:nk=1', str(file_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding='utf-8', errors='replace', timeout=30
        )
        return result.stdout.strip().lower()
    except Exception as e:
        json_log("codec_error", file=str(file_path), stream=stream_specifier, error=str(e))
        return None

# ── Lockfile (prevents concurrent runs on same output dir) ─────────────────────
LOCKFILE_PATH = "/tmp/compressor.lock"

def acquire_lock():
    """Acquire exclusive lock to prevent concurrent runs."""
    try:
        lockfd = os.open(LOCKFILE_PATH, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write PID
        os.write(lockfd, f"{os.getpid()}\n".encode())
        return lockfd
    except (IOError, OSError) as e:
        if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
            json_error("LockfileError", "Another instance is running. Remove /tmp/compressor.lock if stale.", recoverable=False)
            sys.exit(EXIT_FATAL)
        raise

def release_lock(lockfd):
    """Release exclusive lock."""
    try:
        fcntl.flock(lockfd, fcntl.LOCK_UN)
        os.close(lockfd)
        os.unlink(LOCKFILE_PATH)
    except OSError:
        pass

# ── File Classification ───────────────────────────────────────────────────────
def is_regular_file(path):
    """Check if path is a regular file (not fifo, device, symlink, socket)."""
    try:
        stat = os.stat(path)
        return stat.st_mode & 0o170000 == 0o100000  # S_IFREG
    except OSError:
        return False

def is_video_file(file_name):
    return Path(file_name).suffix.lower()[1:] in VIDEO_EXTENSIONS

def is_video_by_probe(path):
    """Fallback: use ffprobe to check if file has a video stream."""
    return len(run_ffprobe(path, 'v')) > 0

def is_correct_format(file_path):
    video_codec = get_codec_name(file_path, 'v:0')
    if not video_codec:
        json_log("skip_unknown_codec", file=str(file_path))
        return True
    if not settings.get('encode_hevc', False) and video_codec in ('hevc', 'h265'):
        json_log("skip_hevc", file=str(file_path), codec=video_codec)
        return True
    desired = VIDEO_ENCODER_CODEC_MAP.get(settings.get('video_encoder', ''), '').lower()
    return video_codec == desired

def has_multiple_audio_or_subtitles(file_path):
    return len(run_ffprobe(file_path, 'a')) > 1 or len(run_ffprobe(file_path, 's')) > 0

# ── Disk Space ────────────────────────────────────────────────────────────────
def check_disk_space(file_path, needed_bytes=None):
    """Check available disk space. Return True if OK, False if low.
    Default: 2x the input file size, minimum 500MB, maximum 10GB."""
    try:
        file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
        if needed_bytes is None:
            needed_bytes = max(min(file_size * 2, 10 * 1024**3), 500 * 1024**2)
        stat = os.statvfs(Path(file_path).parent)
        free = stat.f_bavail * stat.f_frsize
        if free < needed_bytes:
            json_log("disk_space_low", path=str(file_path), free_gb=round(free/1024**3,2), needed_gb=round(needed_bytes/1024**3,2))
            return False
        return True
    except OSError:
        return True

# ── Rename Helpers ────────────────────────────────────────────────────────────
def rename_for_encoding(file_path):
    path = Path(file_path)
    new_path = path.with_name(f"{path.stem}_to_be_encoded{path.suffix}")
    counter = 1
    while new_path.exists():
        new_path = path.with_name(f"{path.stem}_to_be_encoded_{counter}{path.suffix}")
        counter += 1
    path.rename(new_path)
    current_process['original_file'] = str(path)
    current_process['renamed_file'] = str(new_path)
    return new_path

def rename_after_encoding(original_file, encoded_file):
    original_path = Path(original_file)
    encoded_path = Path(encoded_file)
    final_path = original_path.with_suffix(encoded_path.suffix)
    if final_path.exists():
        final_path.unlink()
    # Cross-device fallback: Path.rename() fails across filesystems
    try:
        encoded_path.rename(final_path)
    except OSError as e:
        if e.errno == errno.EXDEV:
            # Cross-device: copy then delete
            shutil.copy2(str(encoded_path), str(final_path))
            encoded_path.unlink()
            json_log("cross_device_fallback", src=str(encoded_path), dst=str(final_path))
        else:
            raise
    return str(final_path)

def copy_metadata(original_file, new_file):
    try:
        shutil.copystat(str(original_file), str(new_file))
    except OSError as e:
        json_log("metadata_copy_error", from_=str(original_file), to_=str(new_file), error=str(e))

# ── Main Conversion ───────────────────────────────────────────────────────────
def convert_to_av1_opus(file_path):
    """Convert video to AV1/Opus with transactional writes and guaranteed cleanup."""
    file_path = Path(file_path)
    result = {
        "status": "pending",
        "file": str(file_path),
        "original_size": None,
        "encoded_size": None,
        "space_saved": 0
    }
    temp_encoded_file_path = None

    try:
        # ── Pre-flight checks ──────────────────────────────────────────────
        if not file_path.exists():
            json_error("FileNotFoundError", f"File not found: {file_path}", recoverable=True, file=str(file_path))
            return 0

        original_size = file_path.stat().st_size
        result["original_size"] = original_size

        if original_size < MIN_FILE_SIZE:
            json_log("skip_too_small", file=str(file_path), size=original_size, min=MIN_FILE_SIZE)
            result["status"] = "skipped"
            return 0

        if not os.access(str(file_path), os.R_OK):
            json_error("PermissionDeniedError", f"No read access: {file_path}", recoverable=True, file=str(file_path))
            return 0

        video_duration = get_video_duration(file_path)
        if not video_duration:
            json_error("DurationError", f"Could not read duration: {file_path}", recoverable=True, file=str(file_path))
            return 0

        # ── Disk space check (enforce, not just warn) ──────────────────────
        if not check_disk_space(file_path):
            json_error("DiskSpaceError", f"Disk space critically low: {file_path}", recoverable=True, file=str(file_path))
            return 0

        # ── Rename phase ───────────────────────────────────────────────────
        renamed_file = rename_for_encoding(file_path)
        json_log("file_renamed", original=str(file_path), temp=str(renamed_file))

        if not os.access(str(renamed_file), os.R_OK | os.W_OK):
            json_error("PermissionDeniedError", f"No access to renamed file: {renamed_file}", recoverable=True, file=str(file_path))
            Path(renamed_file).rename(file_path)
            return 0

        # ── Temp file setup ────────────────────────────────────────────────
        container_ext = '.mkv' if has_multiple_audio_or_subtitles(renamed_file) else '.mp4'
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=container_ext, dir=renamed_file.parent
        )
        temp_encoded_file_path = Path(temp_file.name)
        temp_file.close()
        current_process['temp_encoded_file'] = str(temp_encoded_file_path)
        current_process['original_file'] = str(file_path)
        current_process['renamed_file'] = str(renamed_file)

        # ── Build FFmpeg command ───────────────────────────────────────────
        map_opts = ['-map', '0'] if container_ext == '.mkv' else []
        codec_opts = ['-c:s', 'copy'] if container_ext == '.mkv' else []

        ffmpeg_cmd = ['ffmpeg', '-y']
        if settings.get('hw_accel') in HW_ACCELS and settings.get('hw_accel') != 'software':
            ffmpeg_cmd += ['-hwaccel', settings['hw_accel']]
        # faststart: moov atom at front of MP4 = streamable. MKV uses EBML, flag has no effect.
        output_flags = ['-movflags', '+faststart'] if container_ext == '.mp4' else []
        ffmpeg_cmd += [
            '-i', str(renamed_file), *map_opts,
            '-c:v', settings.get('video_encoder', 'libx264'),
            '-crf', settings.get('video_crf', '30'),
            '-b:v', settings.get('video_bitrate', '0'),
            '-c:a', settings.get('audio_encoder', 'libopus'),
            '-b:a', settings.get('audio_bitrate', '128k'),
            *codec_opts, '-map_metadata', '0', *output_flags,
            str(temp_encoded_file_path), '-progress', 'pipe:1'
        ]

        json_log("encode_start", file=str(file_path), cmd=ffmpeg_cmd)

        # ── Run FFmpeg with timeout + SIGINT propagation ───────────────────
        env = os.environ.copy()
        env['IMAGEIO_FFMPEG_NO_PREVENT_SIGINT'] = '1'  # Critical: propagates Ctrl+C to ffmpeg child

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding='utf-8', errors='replace',
            env=env
        )
        current_process['process'] = process

        # ── Async progress reader (avoids pipe deadlock) ────────────────────
        progress_buf = []
        last_printed_progress = 0

        def read_progress():
            nonlocal last_printed_progress
            while True:
                char = process.stdout.read(1)  # type: ignore[union-attr]
                if not char:
                    break
                if char == '\n':
                    line = ''.join(progress_buf)
                    progress_buf.clear()
                    if "out_time_ms" in line:
                        try:
                            time_ms = int(line.split('=')[-1].strip())
                            progress = min(100, int((time_ms / (video_duration * 1_000_000)) * 100))
                            if progress >= last_printed_progress + 10:
                                sys.stdout.write(f"\r  {progress:.0f}%")
                                sys.stdout.flush()
                                last_printed_progress = progress
                        except (ValueError, IndexError):
                            pass
                else:
                    progress_buf.append(char)

        progress_thread = threading.Thread(target=read_progress, daemon=True)
        progress_thread.start()

        try:
            exit_code = process.wait(timeout=FFMPEG_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            json_log("encode_timeout", file=str(file_path), timeout_sec=FFMPEG_TIMEOUT_SEC)
            process.terminate()
            process.wait(timeout=5)
            json_error("EncodeTimeoutError", f"FFmpeg timed out after {FFMPEG_TIMEOUT_SEC}s: {file_path}", recoverable=True, file=str(file_path))
            if temp_encoded_file_path.exists():
                temp_encoded_file_path.unlink()
            if renamed_file.exists():
                renamed_file.rename(file_path)
            return 0

        progress_thread.join(timeout=2)
        sys.stdout.write("\n")

        # ── Post-encoding verification ────────────────────────────────────
        if exit_code != 0:
            json_error(
                "FFmpegError",
                f"FFmpeg failed with exit code {exit_code}: {file_path}",
                recoverable=True,
                file=str(file_path),
                exit_code=exit_code
            )
            if temp_encoded_file_path.exists():
                temp_encoded_file_path.unlink()
            if renamed_file.exists():
                renamed_file.rename(file_path)
            return 0

        # CRITICAL: verify output before destroying source
        if not (temp_encoded_file_path.exists() and temp_encoded_file_path.stat().st_size > 0):
            json_error(
                "EncodeOutputMissing",
                f"Encoding produced empty or missing output: {file_path}",
                recoverable=True,
                file=str(file_path)
            )
            if renamed_file.exists():
                renamed_file.rename(file_path)
            return 0

        # ── Atomic commit: temp → final location ───────────────────────────
        encoded_file = file_path.with_suffix('').with_suffix(container_ext)
        shutil.move(str(temp_encoded_file_path), str(encoded_file))
        copy_metadata(renamed_file, encoded_file)
        final_file = str(encoded_file)

        new_size = Path(final_file).stat().st_size
        space_saved = original_size - new_size

        # ── Space-saver guard: discard output if larger than input ───────────
        if settings.get('space_saver') and space_saved < 0:
            # Output is larger — discard it, revert to original
            json_log("skip_space_saver", file=str(file_path),
                     original_mb=round(original_size/1024**2,2),
                     new_mb=round(new_size/1024**2,2),
                     wasted_mb=round(abs(space_saved)/1024**2,2))
            # Delete the too-large output
            if Path(final_file).exists():
                Path(final_file).unlink()
            # Revert renamed source back to original name
            if renamed_file.exists():
                renamed_file.rename(file_path)
            if settings.get('mode') == 'basic':
                print(f"✗ Skipped (larger): {file_path}")
                print(f"  {original_size/1024**2:.1f} MB → {new_size/1024**2:.1f} MB (would grow)")
            result.update({"status": "skipped", "encoded_size": new_size, "space_saved": 0})
            json_success(file_path, original_size, new_size, 0)
            current_process.clear()
            return 0

        # Output accepted — clean up the renamed source
        if renamed_file.exists():
            renamed_file.unlink()

        # ── Success output ─────────────────────────────────────────────────
        json_log("encode_success", file=str(file_path), original_mb=round(original_size/1024**2,2), new_mb=round(new_size/1024**2,2), saved_mb=round(space_saved/1024**2,2))

        if settings.get('mode') == 'basic':
            print(f"✓ Converted: {file_path}")
            print(f"  {original_size/1024**2:.1f} MB → {new_size/1024**2:.2f} MB (saved {abs(space_saved)/1024**2:.2f} MB)")

        result.update({
            "status": "success",
            "encoded_size": new_size,
            "space_saved": space_saved
        })
        json_success(file_path, original_size, new_size, space_saved)

        current_process.clear()
        return space_saved

    except OSError as e:
        json_error("OSError", str(e), recoverable=True, file=str(file_path))
        clean_up_current_file()
        return 0
    except Exception as e:
        json_error(type(e).__name__, str(e), recoverable=True, file=str(file_path))
        clean_up_current_file()
        return 0
    finally:
        # Guaranteed cleanup — runs on success, error, signal, or timeout
        clean_up_current_file()

# ── Directory Walker ──────────────────────────────────────────────────────────
def search_and_convert(target_directory, dry_run=False):
    """Recursively find and convert video files."""
    stats = {"total": 0, "converted": 0, "skipped": 0, "errors": 0, "saved_bytes": 0}
    target = Path(target_directory)

    if not target.is_dir():
        json_error("NotADirectoryError", f"Not a directory: {target_directory}", recoverable=False)
        return stats

    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_FILES and not d.startswith('._')]
        for fname in files:
            if fname in SKIP_FILES or fname.startswith('._'):
                continue
            file_path = target / Path(root).relative_to(target) / fname

            # Classify: extension-based or probe-based (no extension + video stream)
            video_candidate = is_video_file(fname)
            if not video_candidate:
                # No extension — probe fallback only for files large enough to be video
                try:
                    if file_path.stat().st_size >= MIN_FILE_SIZE and is_video_by_probe(file_path):
                        video_candidate = True
                except OSError:
                    video_candidate = False

            if not video_candidate:
                continue

            # Skip non-regular files (named pipes, devices, sockets, symlinks)
            if not is_regular_file(file_path):
                json_log("skip_non_regular", file=str(file_path))
                stats["skipped"] += 1
                continue

            stats["total"] += 1

            try:
                file_size = file_path.stat().st_size if file_path.exists() else 0
                if file_size < MIN_FILE_SIZE:
                    json_log("skip_too_small_walk", file=str(file_path))
                    stats["skipped"] += 1
                    continue
                if is_correct_format(file_path):
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    json_log("dry_run_would_convert", file=str(file_path), size_mb=round(file_size/1024**2,2))
                    stats["converted"] += 1
                    continue

                saved = convert_to_av1_opus(file_path)
                if saved > 0:
                    stats["converted"] += 1
                    stats["saved_bytes"] += saved
                elif saved < 0:
                    # Encoded but output larger than input — still converted, just negative savings
                    stats["converted"] += 1
                    stats["saved_bytes"] += saved
                else:  # saved == 0
                    stats["skipped"] += 1
            except Exception as e:
                json_error("UnexpectedError", str(e), recoverable=True, file=str(file_path))
                stats["errors"] += 1

    json_log("batch_complete", dry_run=dry_run, **stats)
    print(f"\n── Results {'(dry-run) ' if dry_run else ''}────────────────")
    print(f"  Total:    {stats['total']}")
    print(f"  Converted: {stats['converted']}")
    print(f"  Skipped:  {stats['skipped']}")
    print(f"  Errors:    {stats['errors']}")
    if not dry_run:
        net = stats['saved_bytes'] / 1024**2
        sign = '+' if net >= 0 else ''
        print(f"  Space saved: {sign}{net:.1f} MB")
    else:
        print(f"  (dry run — no files encoded)")

    return stats

# ── Curses UI ─────────────────────────────────────────────────────────────────
def curses_menu(stdscr, title, options, descriptions, recommended, selected_idx=0):
    curses.curs_set(0)
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)

    while True:
        stdscr.clear()
        try:
            stdscr.addstr(0, 0, title[:w], curses.A_BOLD)
        except curses.error:
            pass
        for idx, option in enumerate(options):
            y = h // 2 - len(options) // 2 + idx
            if 0 <= y < h:
                color = curses.color_pair(1) if option in recommended else curses.color_pair(2)
                try:
                    desc = descriptions.get(option, 'No description')[:w - 4]
                    display = f"{option}: {desc}"
                    stdscr.addstr(y, 2, display, color | (curses.A_REVERSE if idx == selected_idx else curses.A_NORMAL))
                except curses.error:
                    pass
        try:
            stdscr.addstr(h - 1, 0, "↑↓ navigate  Enter select  Esc cancel"[:w])
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP:
            selected_idx = (selected_idx - 1) % max(len(options), 1)
        elif key == curses.KEY_DOWN:
            selected_idx = (selected_idx + 1) % max(len(options), 1)
        elif key in (10, 13):
            return selected_idx
        elif key == 27:
            return None

def configure_settings(stdscr):
    global settings
    settings.setdefault('hw_accel', None)
    settings.setdefault('video_encoder', 'libx264')
    settings.setdefault('video_crf', '30')
    settings.setdefault('video_bitrate', '0')
    settings.setdefault('audio_encoder', 'libopus')
    settings.setdefault('audio_bitrate', '128k')
    settings.setdefault('encode_hevc', False)
    settings.setdefault('mode', 'basic')

    accel_options = HW_ACCELS + ['software']
    accel_desc = HW_ACCEL_INFO.copy()
    accel_desc['software'] = "Software: CPU-based encoding, no hardware acceleration."
    accel_idx = curses_menu(stdscr, "Hardware Acceleration", accel_options, accel_desc, RECOMMENDED_HW_ACCELS)
    if accel_idx is not None:
        settings['hw_accel'] = accel_options[accel_idx]
        settings['video_encoder'] = VIDEO_ENCODERS.get(settings['hw_accel'], VIDEO_ENCODERS['software'])[0]

    enc_options = VIDEO_ENCODERS.get(settings.get('hw_accel', 'software'), VIDEO_ENCODERS['software'])
    enc_desc = {e: f"{e}: → {VIDEO_ENCODER_CODEC_MAP.get(e, '').upper()}" for e in enc_options}
    enc_idx = curses_menu(stdscr, "Video Encoder", enc_options, enc_desc, [])
    if enc_idx is not None:
        settings['video_encoder'] = enc_options[enc_idx]

    for label, options, key in [
        ("Video CRF", CRF_OPTIONS, 'video_crf'),
        ("Video Bitrate", VIDEO_BITRATES, 'video_bitrate'),
        ("Audio Encoder", AUDIO_ENCODERS, 'audio_encoder'),
        ("Audio Bitrate", AUDIO_BITRATES, 'audio_bitrate'),
    ]:
        current = settings.get(key, options[0])
        sel = curses_menu(stdscr, f"{label} ({current})", options, {}, [])
        if sel is not None:
            settings[key] = options[sel]

    hevc_idx = curses_menu(stdscr, "Encode HEVC?", ["Yes", "No"], {}, [])
    if hevc_idx is not None:
        settings['encode_hevc'] = (hevc_idx == 0)

    mode_idx = curses_menu(stdscr, "Mode", ["Basic", "Advanced"], {}, [])
    if mode_idx is not None:
        settings['mode'] = ['basic', 'advanced'][mode_idx]

    if curses_menu(stdscr, "Save config?", ["Yes", "No"], {}, []) == 0:
        save_config()

def get_directory(stdscr):
    curses.curs_set(1)
    stdscr.clear()
    stdscr.addstr(0, 0, "Directory: ")
    stdscr.refresh()
    d = ""
    while True:
        key = stdscr.getch()
        if key in (10, 13):
            if Path(d).is_dir():
                return d
            stdscr.addstr(2, 0, "Invalid. Press any key.")
            stdscr.getch()
            stdscr.clear()
            stdscr.addstr(0, 0, "Directory: ")
            d = ""
        elif key == 27:
            return None
        elif key in (curses.KEY_BACKSPACE, 127):
            d = d[:-1]
            stdscr.clear()
            stdscr.addstr(0, 0, "Directory: " + d)
        elif 32 <= key <= 126:
            d += chr(key)
            stdscr.addstr(0, 0, "Directory: " + d)
        stdscr.refresh()

def main(stdscr):
    check_ffmpeg()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    stdscr.bkgd(' ', curses.color_pair(2))
    probe_hw_accels()
    load_config()
    configure_settings(stdscr)
    target = get_directory(stdscr)
    if target:
        search_and_convert(target)

# ── Headless / CLI Entry Point ────────────────────────────────────────────────
def run_headless(args):
    """Run encoding without curses UI (headless / agent mode)."""
    global settings
    # Verify ffmpeg/ffprobe are available (same check as curses mode)
    check_ffmpeg()
    # Apply CLI overrides to defaults
    settings.setdefault('hw_accel', None)
    settings.setdefault('video_encoder', 'libx264')
    settings.setdefault('video_crf', '30')
    settings.setdefault('video_bitrate', '0')
    settings.setdefault('audio_encoder', 'libopus')
    settings.setdefault('audio_bitrate', '128k')
    settings.setdefault('encode_hevc', False)
    settings.setdefault('mode', 'basic')

    if args.encoder:
        settings['video_encoder'] = args.encoder
        # Explicit encoder override → disable hw_accel to avoid mismatch
        settings['hw_accel'] = 'software'
        settings['_encoder_overridden'] = True
    else:
        # Always force software encoding (disable HW acceleration)
        settings['hw_accel'] = 'software'
        settings['video_encoder'] = 'libsvtav1'
        settings['_encoder_overridden'] = True

    if args.audio_encoder:
        settings['audio_encoder'] = args.audio_encoder
    if args.audio_bitrate:
        settings['audio_bitrate'] = args.audio_bitrate
    if args.mode:
        settings['mode'] = args.mode
    if args.encode_hevc:
        settings['encode_hevc'] = True
    if args.space_saver:
        settings['space_saver'] = True

    json_log("headless_start", args=vars(args))
    json_log("encoder_cli_override", encoder=settings['video_encoder'], hw_accel=settings.get('hw_accel'))
    load_config()
    stats = search_and_convert(args.directory, dry_run=args.dry_run)
    return stats

if __name__ == "__main__":
    args = parse_args()

    # If no directory given and curses unavailable → print help
    if not args.directory and not _curses_imported:
        print("No directory specified and curses is not available.")
        print("Usage: python compressor.py /path/to/videos [--crf 25]")
        sys.exit(EXIT_FATAL)

    # If directory provided → headless mode (no curses)
    if args.directory:
        lockfd = acquire_lock()
        try:
            run_headless(args)
        finally:
            release_lock(lockfd)
        sys.exit(EXIT_SUCCESS)

    # No directory → curses mode (interactive)
    if not _curses_imported:
        print("curses not available. Please provide a directory argument:")
        print("  python compressor.py /path/to/videos")
        sys.exit(EXIT_FATAL)

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)