"""
Speech-to-Text модуль на базі Faster Whisper
"""
import numpy as np
import sounddevice as sd
from typing import Optional
from faster_whisper import WhisperModel


class SpeechToText:
    """Розпізнавання мовлення"""

    def __init__(self, model_size: str = "base", device: str = "cpu", language: str = "uk"):
        """
        Ініціалізація STT

        Args:
            model_size: Розмір моделі Whisper (tiny, base, small, medium, large)
            device: cpu або cuda
            language: Мова розпізнавання (uk, en, ru, тощо)
        """
        self.model_size = model_size
        self.device = device
        self.language = language
        self.model = None
        self.sample_rate = 16000  # Whisper працює з 16kHz

        print(f"Завантаження Whisper моделі '{model_size}'...")
        self._load_model()

    def _load_model(self):
        """Завантажити модель Whisper"""
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8"  # Оптимізація для швидкості
            )
            print("Модель Whisper завантажена")
        except Exception as e:
            print(f"Помилка завантаження моделі: {e}")
            raise

    def record_audio(self, duration: int = 5) -> np.ndarray:
        """
        Записати аудіо з мікрофона

        Args:
            duration: Тривалість запису в секундах

        Returns:
            Numpy array з аудіо даними
        """
        print(f"Запис {duration} секунд...")
        audio = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32
        )
        sd.wait()  # Чекати завершення запису
        print("Запис завершено")
        return audio.flatten()

    def transcribe(self, audio: np.ndarray) -> Optional[str]:
        """
        Розпізнати текст з аудіо

        Args:
            audio: Аудіо дані (numpy array)

        Returns:
            Розпізнаний текст або None
        """
        if self.model is None:
            print("Модель не завантажена")
            return None

        try:
            # Whisper очікує float32 array
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Транскрибувати
            segments, info = self.model.transcribe(
                audio,
                language=self.language,
                beam_size=5,
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            # Зібрати текст зі всіх сегментів
            text = " ".join([segment.text.strip() for segment in segments])

            return text.strip() if text else None

        except Exception as e:
            print(f"Помилка розпізнавання: {e}")
            return None

    def transcribe_from_file(self, audio_file: str) -> Optional[str]:
        """
        Розпізнати текст з аудіо файлу

        Args:
            audio_file: Шлях до аудіо файлу

        Returns:
            Розпізнаний текст або None
        """
        if self.model is None:
            print("Модель не завантажена")
            return None

        try:
            segments, info = self.model.transcribe(
                audio_file,
                language=self.language,
                beam_size=5
            )

            text = " ".join([segment.text.strip() for segment in segments])
            return text.strip() if text else None

        except Exception as e:
            print(f"Помилка розпізнавання з файлу: {e}")
            return None

    def listen_and_transcribe(self, duration: int = 5) -> Optional[str]:
        """
        Записати і розпізнати мовлення

        Args:
            duration: Тривалість запису

        Returns:
            Розпізнаний текст
        """
        audio = self.record_audio(duration)
        return self.transcribe(audio)


# Простий тест модуля
if __name__ == "__main__":
    stt = SpeechToText(model_size="base", language="uk")
    print("\nГотовий до розпізнавання. Говоріть...")
    text = stt.listen_and_transcribe(duration=5)

    if text:
        print(f"\nРозпізнано: {text}")
    else:
        print("\nНе вдалося розпізнати мовлення")
