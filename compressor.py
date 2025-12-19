import ffmpeg
import os
import cv2
import imageio_ffmpeg
import shutil
import subprocess
import re
import threading
from PIL import Image

def get_ffmpeg_path():
    """Returns the path to the ffmpeg executable bundled with imageio-ffmpeg."""
    try:
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(path):
            return path
        else:
            print(f"Warning: imageio-ffmpeg returned path that doesn't exist: {path}")
            return "ffmpeg"
    except Exception as e:
        print(f"Error finding ffmpeg: {e}")
        return "ffmpeg" # Fallback to system PATH

def get_video_info(file_path):
    """
    Get video metadata using OpenCV.
    Returns dict with width, height, duration (seconds).
    """
    cap = None
    try:
        print(f"Getting video info for: {file_path}")
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return None
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = 0
        if fps > 0:
            duration = frame_count / fps
            
        return {'width': width, 'height': height, 'duration': duration}
    except Exception as e:
        print(f"Error probing video with OpenCV: {e}")
        return None
    finally:
        if cap:
            cap.release()

def get_thumbnail(file_path):
    """
    Extract the first frame of the video as an image for preview.
    Returns: PIL Image or None
    """
    cap = None
    try:
        cap = cv2.VideoCapture(file_path)
        ret, frame = cap.read()
        if ret:
            # Convert to RGB (OpenCV uses BGR)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(frame_rgb)
        return None
    except Exception as e:
        print(f"Error getting thumbnail: {e}")
        return None
    finally:
        if cap:
            cap.release()

def parse_time_str(time_str):
    """Converts HH:MM:SS.xx to seconds."""
    try:
        # Standard filter format often comes as HH:MM:SS.xx
        # Sometimes handle different formats if necessary
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        return 0
    except Exception:
        return 0

def compress_video(input_path, output_path, target_height, total_duration=0, progress_callback=None, stop_event=None):
    """
    Compress video using subprocess to parse progress.
    stop_event: threading.Event to check for cancellation
    """
    process = None
    try:
        ffmpeg_exe = get_ffmpeg_path()
        print(f"Using FFmpeg path: {ffmpeg_exe}")
        
        # Check permissions/existence just in case
        if not os.path.exists(input_path):
            print("Input file not found.")
            return False

        cmd = [
            ffmpeg_exe,
            '-y', 
            '-i', input_path,
            '-vf', f'scale=-2:{target_height}',
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'medium',
            '-c:a', 'aac',
            output_path
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, # We parse stderr for progress
            universal_newlines=True,
            startupinfo=startupinfo
        )
        
        time_pattern = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d+)")
        
        while True:
            # Check for cancellation
            if stop_event and stop_event.is_set():
                print("Compression cancelled.")
                process.kill()
                return False

            # Read line-by-line. 
            # Note: loop might block on readline if no output, but ffmpeg usually verbose.
            line = process.stderr.readline()
            
            if not line and process.poll() is not None:
                # Process finished and no more output
                break
            
            if line:
                # print(line.strip()) # Debug
                if progress_callback and total_duration > 0:
                    match = time_pattern.search(line)
                    if match:
                        time_str = match.group(1)
                        current_seconds = parse_time_str(time_str)
                        if total_duration > 0:
                            percentage = min(current_seconds / total_duration, 1.0)
                            progress_callback(percentage)
        
        if stop_event and stop_event.is_set(): # Double check
             return False
             
        # Check return code
        if process.returncode != 0:
             print(f"FFmpeg exited with error code: {process.returncode}")
             return False

        return True
        
    except Exception as e:
        print(f"General Error during compression: {e}")
        # Ensure process is killed if exception happens (e.g. keyboard interrupt in console, or other error)
        if process:
            try:
                process.kill()
            except:
                pass
        return False
