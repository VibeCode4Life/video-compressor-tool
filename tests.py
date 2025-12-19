import unittest
from unittest.mock import patch, MagicMock
import os
import sys
# Ensure PIL is patched if needed, but since we moved import, we can patch global PIL.Image or compressor.Image
from compressor import get_ffmpeg_path, get_video_info, get_thumbnail, parse_time_str, compress_video

class TestCompressor(unittest.TestCase):

    @patch('compressor.imageio_ffmpeg.get_ffmpeg_exe')
    @patch('compressor.os.path.exists')
    def test_get_ffmpeg_path_success(self, mock_exists, mock_get_exe):
        mock_get_exe.return_value = '/path/to/ffmpeg'
        mock_exists.return_value = True
        path = get_ffmpeg_path()
        self.assertEqual(path, '/path/to/ffmpeg')

    @patch('compressor.imageio_ffmpeg.get_ffmpeg_exe')
    @patch('compressor.os.path.exists')
    def test_get_ffmpeg_path_fallback(self, mock_exists, mock_get_exe):
        mock_get_exe.return_value = '/path/to/ffmpeg'
        mock_exists.return_value = False
        path = get_ffmpeg_path()
        self.assertEqual(path, 'ffmpeg')

    @patch('compressor.cv2.VideoCapture')
    def test_get_video_info_success(self, mock_cap_cls):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = [1920.0, 1080.0, 30.0, 300.0] # Width, Height, FPS, FrameCount
        mock_cap_cls.return_value = mock_cap

        info = get_video_info("dummy.mp4")
        self.assertEqual(info['width'], 1920)
        self.assertEqual(info['height'], 1080)
        self.assertEqual(info['duration'], 10.0) # 300 frames / 30 fps
        mock_cap.release.assert_called_once()

    @patch('compressor.cv2.VideoCapture')
    def test_get_video_info_fail(self, mock_cap_cls):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cap_cls.return_value = mock_cap

        info = get_video_info("dummy.mp4")
        self.assertIsNone(info)
        mock_cap.release.assert_called_once()

    @patch('compressor.cv2.VideoCapture')
    @patch('compressor.Image.fromarray')
    @patch('compressor.cv2.cvtColor') 
    def test_get_thumbnail_success(self, mock_cvt, mock_fromarray, mock_cap_cls):
        mock_cap = MagicMock()
        mock_cap.read.return_value = (True, MagicMock()) # Ret, Frame
        mock_cap_cls.return_value = mock_cap
        
        # Setup mocks
        mock_cvt.return_value = "rgb_frame"
        mock_fromarray.return_value = "pil_image"

        thumb = get_thumbnail("dummy.mp4")
        self.assertEqual(thumb, "pil_image")
        mock_cap.release.assert_called_once()
        mock_cvt.assert_called()

    def test_parse_time_str(self):
        self.assertEqual(parse_time_str("00:00:10.50"), 10.5)
        self.assertEqual(parse_time_str("01:01:01.00"), 3661.0)
        self.assertEqual(parse_time_str("invalid"), 0)

    @patch('compressor.get_ffmpeg_path')
    @patch('compressor.subprocess.Popen')
    @patch('compressor.os.path.exists')
    def test_compress_video_success(self, mock_exists, mock_popen, mock_get_path):
        mock_exists.return_value = True
        mock_get_path.return_value = "ffmpeg"
        
        process_mock = MagicMock()
        # Readline returns data then empty string indefinitely
        process_mock.stderr.readline.side_effect = [
            "frame=  1 fps=0.0 q=0.0 size=       0kB time=00:00:05.00 bitrate=N/A speed=   0x",
            ""
        ]
        # Poll: Only called when readline is empty. Return 0 to indicate finish.
        process_mock.poll.return_value = 0 
        process_mock.returncode = 0
        mock_popen.return_value = process_mock

        callback = MagicMock()
        success = compress_video("in.mp4", "out.mp4", 720, total_duration=10, progress_callback=callback)
        
        self.assertTrue(success)
        callback.assert_called() 

if __name__ == '__main__':
    unittest.main()
