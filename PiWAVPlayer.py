import wave
import pyaudio
import logging
import time
from typing import Optional


class PiWAVPlayer:
    """
    Класс плеера для проигрывания wav файлов
    """
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.audiostream: Optional[pyaudio.Stream] = None
        self.filestream: Optional[wave.Wave_read] = None
        self.filename = ""
        self.chunk = 0

    def load(self, filename: str) -> bool:
        """
        Функция для загрузки WAV-файла
        """
        try:
            self.filestream = wave.open(filename, 'rb')
            self.filename = filename
            return True
        except (FileNotFoundError, wave.Error) as e:
            logging.error(f"Файл не загружен! Ошибка: {str(e)}")
            return False

    def audio_stream_callback(self, in_data, frame_count, time_info, status):
        """
        Функция-callback для воспроизведения с помощью PyAudio
        """
        if self.filestream:
            data = self.filestream.readframes(frame_count)
            return (data, pyaudio.paContinue)
        return (None, pyaudio.paCanNotReadFromACallbackStream)


    def play(self) -> None:
        """
        Запускает воспроизведение загруженного файла
        """
        if self.filestream is None:
            if not self.filename:
                logging.error("Воспроизведение не начато! Файл не загружен!")
                return
            is_loaded = self.load(self.filename)
            if not is_loaded or self.filestream is None:
                logging.error("Воспроизведение не начато! " \
                        "Файл испорчен или отсутствует!")
                return

        assert self.filestream is not None

        self.audiostream = self.p.open(
                format=self.p.get_format_from_width(self.filestream.getsampwidth()),
                channels=self.filestream.getnchannels(),
                rate=self.filestream.getframerate(),
                output=True,
                stream_callback=self.audio_stream_callback)

        logging.info(f"Начало воспроизведения: {self.filename}")
       
        try:
            while self.audiostream.is_active():
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        self.stop(type="standart")

    def stop(self, type="") -> None:
        """
        Останавливает воспроизведение запущенного файла
        """
        if self.audiostream:
            self.audiostream.stop_stream()
            self.audiostream.close()
            self.audiostream = None
        elif type not in ("standart", "terminate"):
            logging.warning("Ни один файл не воспроизводится!")

        if self.filestream:
            self.filestream.close()
            self.filestream = None
        elif type not in ("standart", "terminate"):
            logging.warning("Ни один файл не загружен!")
        
        if type != "terminate":
            logging.info("Воспроизведение остановлено")

    def __del__(self):
        """
        Деструктор для освобождения PyAudio
        """
        self.stop(type="terminate")
        self.p.terminate()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
            prog='PiWAVPlayer',
            description='Simple WAV player')

    parser.add_argument('filename')

    args = parser.parse_args()

    logging.getLogger().setLevel(logging.INFO)

    player = PiWAVPlayer()
    is_loaded = player.load(args.filename)
    if is_loaded:
        player.play()
    
