import wave
import pyaudio
import logging
import time
import numpy as np
from typing import Optional
from ctypes import CFUNCTYPE, c_char_p, c_int, cdll

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)


def py_error_handler(filename, line, function, err, fmt):  # block logs from asound
    pass


c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
asound = cdll.LoadLibrary('libasound.so')
asound.snd_lib_error_set_handler(c_error_handler)


class PiWAVPlayer:
    '''Player for wav files'''

    def __init__(self):
        self._p = pyaudio.PyAudio()
        self._audiostream: Optional[pyaudio.Stream] = None
        self._filestream: Optional[wave.Wave_read] = None
        self._filename = ''
        self._is_loop = False
        self._volume = 1  # float, range: 0-1
        self._position = 0
        self._logger = None

    def load(self, filename: str) -> bool:
        '''Loads wav files'''
        try:
            self._filestream = wave.open(filename, 'rb')
            self._filename = filename
            return True
        except (FileNotFoundError, wave.Error) as e:
            if self._logger:
                self._logger.error(f'File has not loaded! Error: {str(e)}')
            return False

    def audio_stream_callback(self, in_data, frame_count, time_info, status):
        '''Callback funtion for playback using PyAudio'''
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
        '''Starts playback of loaded file'''
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
        self.stop(type='standart')

    def stop(self, type: str = '') -> None:
        '''Stops playback'''
        if self._audiostream:
            self._audiostream.stop_stream()
            self._audiostream.close()
            self._audiostream = None
        elif type not in ('standart', 'terminate'):
            if self._logger:
                self._logger.warning('Not a single file is playing!')

        if self._filestream:
            self._filestream.close()
            self._filestream = None
            self._filename = ''
        elif type not in ('standart', 'terminate'):
            if self._logger:
                self._logger.warning('Not a single file is loaded!')

        if type != 'terminate':
            if self._logger:
                self._logger.info('Playback is stopped')

    def set_volume(self, volume: float) -> float:
        '''Sets volume level'''
        if 0 <= volume <= 1:
            self._volume = volume
            return self._volume
        if self._logger:
            self._logger.warning('Volume must be in 0.0..1.0')
        return -1

    def get_volume(self) -> float:
        '''Gets volume level'''
        return self._volume

    def set_loop_mode(self, is_loop: bool) -> bool:
        '''Sets play mode'''
        self._is_loop = is_loop
        return self._is_loop

    def get_loop_mode(self) -> bool:
        '''Gets play mode'''
        return self._is_loop

    def set_logger(self, logger: logging.Logger) -> None:
        '''Sets play mode'''
        self._logger = logger
        return

    def __del__(self):
        '''Free PyAudio'''
        self.stop(type='terminate')
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

    is_loaded = player.load(args.filename)
    if is_loaded:
        player.play()
