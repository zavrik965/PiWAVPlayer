'''
Player for sounds in WAV-formats
'''

import logging
import time
import wave
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll
from typing import Optional, Tuple, Mapping, Union

import numpy as np
import pyaudio

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


def py_error_handler(_filename, _line, _function, _err, _fmt):
    '''
    block logs from asound
    '''


c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
asound = cdll.LoadLibrary('libasound.so')
asound.snd_lib_error_set_handler(c_error_handler)


class PiWAVPlayer:
    '''A simple WAV player class'''

    def __init__(self) -> None:
        '''
        Initialize WAV player

        This sets up PyAudio for playback and initializes necessary components.
        '''
        self._p = pyaudio.PyAudio()
        self._audiostream: Optional[pyaudio.Stream] = None
        self._filestream: Optional[wave.Wave_read] = None
        self._filename = ''
        self._is_loop = False
        self._volume = 1  # float, range: 0-1
        self._position = 0
        self._logger = None

    def load(self, filename: str) -> bool:
        '''
        Load a WAV file into the player.

        Args:
            filename (str): The path to the WAV file to be loaded.

        Returns:
            bool: True if loading was successful, False otherwise.
        '''
        try:
            self._filestream = wave.open(filename, 'rb')
            self._filename = filename
            return True
        except (FileNotFoundError, wave.Error) as e:
            if self._logger:
                self._logger.error(f'File has not loaded! Error: {str(e)}')
            return False

    def audio_stream_callback(
        self,
        _in_data: Union[int, None],
        frame_count: int,
        _time_info: Mapping[str, float],
        _status: int,
    ) -> Tuple[Union[int, None], int]:
        '''
        Callback function for playback using PyAudio.

        Args:
            _in_data (Union[int, None]): Input data from previous buffer.
            frame_count (int): Number of frames to process.
            _time_info (Mapping[str, float]): Time information passed by ASound.
            _status (int): Status code passed by ASound.

        Returns:
            Tuple[Union[int, None], int]: Data to send back and type of data requested.
        '''
        if self._filestream:
            start_pos = self._position
            end_pos = start_pos + frame_count
            if end_pos > self._filestream.getnframes() and self._is_loop:
                data = self._filestream.readframes(frame_count)
                remaining = end_pos - self._filestream.getnframes()
                self._filestream.rewind()
                data += self._filestream.readframes(remaining)
                self._position = remaining
            else:
                data = self._filestream.readframes(frame_count)
                self._position += frame_count
            audio_data = np.frombuffer(data, dtype=np.int16)
            audio_data = (audio_data * self._volume).astype(np.int16)
            return (audio_data.tobytes(), pyaudio.paContinue)
        return (None, pyaudio.paCanNotReadFromACallbackStream)

    def play(self) -> None:
        '''
        Start playback of the loaded file.

        This method ensures that a file is loaded before attempting playback.
        It handles both normal and looped playback modes.
        '''
        if self._filestream is None:
            if not self._filename:
                if self._logger:
                    self._logger.error('Playback has not started! File is not loaded!')
                return
            is_loaded = self.load(self._filename)
            if not is_loaded or self._filestream is None:
                if self._logger:
                    self._logger.error(
                        'Playback has not started! File is corrupted or does not exist!'
                    )
                return

        assert self._filestream is not None

        self._audiostream = self._p.open(
            format=self._p.get_format_from_width(self._filestream.getsampwidth()),
            channels=self._filestream.getnchannels(),
            rate=self._filestream.getframerate(),
            output=True,
            stream_callback=self.audio_stream_callback,
        )

        if self._logger:
            self._logger.info(f'Playback started: {self._filename}')

        try:
            while self._audiostream and self._audiostream.is_active():
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        self.stop(req_type='standart')

    def stop(self, req_type: str = '') -> None:
        '''
        Stop playback.

        Args:
            req_type (str, optional): Type of request to send back.
            Defaults to 'standard'.
        '''
        if self._audiostream:
            self._audiostream.stop_stream()
            self._audiostream.close()
            self._audiostream = None
        elif req_type not in ('standart', 'terminate'):
            if self._logger:
                self._logger.warning('Not a single file is playing!')

        if self._filestream:
            self._filestream.close()
            self._filestream = None
            self._filename = ''
        elif req_type not in ('standart', 'terminate'):
            if self._logger:
                self._logger.warning('Not a single file is loaded!')

        if req_type != 'terminate':
            if self._logger:
                self._logger.info('Playback is stopped')

    def set_volume(self, volume: float) -> float:
        '''
        Set the volume level.

        Args:
            volume (float): Volume value between 0.0 and 1.0

        Returns:
            float: The new volume level
        '''
        if 0 <= volume <= 1:
            self._volume = volume
            return self._volume
        if self._logger:
            self._logger.warning('Volume must be in 0.0..1.0')
        return -1

    def get_volume(self) -> float:
        '''
        Get the current volume level.

        Returns:
            float: The current volume level (between 0.0 and 1.0)
        '''
        return self._volume

    def set_loop_mode(self, is_loop: bool) -> bool:
        '''
        Set play mode to loop or not.

        Args:
            is_loop (bool): True if looping should occur, False otherwise

        Returns:
            bool: The new loop state
        '''
        self._is_loop = is_loop
        return self._is_loop

    def get_loop_mode(self) -> bool:
        '''
        Get the current play loop mode.

        Returns:
            bool: True if playing in loop mode, False otherwise
        '''
        return self._is_loop

    def set_logger(self, logger: logging.Logger) -> None:
        '''
        Set the logger for this player instance.
        '''
        self._logger = logger

    def __del__(self):
        '''
        Cleanup method called when the object is garbage collected.

        This stops playback and terminates PyAudio.
        '''
        self.stop(req_type='terminate')
        self._p.terminate()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        prog='PiWAVPlayer', description='Simple WAV player'
    )

    parser.add_argument('filename')

    args = parser.parse_args()

    logging.getLogger().setLevel(logging.INFO)

    player = PiWAVPlayer()

    player.set_logger(logging.getLogger())

    if player.load(args.filename):
        player.play()
