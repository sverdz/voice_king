"""
Wake Word Detection модуль на базі Porcupine
"""
import struct
import pyaudio
import pvporcupine
from typing import Optional, Callable


class WakeWordDetector:
    """Детектор кодового слова (wake word)"""

    def __init__(self, access_key: str, keywords: list = None, sensitivities: list = None):
        """
        Ініціалізація wake word detector

        Args:
            access_key: Picovoice access key (отримати на https://console.picovoice.ai/)
            keywords: Список ключових слів (наприклад, ['porcupine', 'computer'])
            sensitivities: Чутливість для кожного слова (0.0 - 1.0)
        """
        self.access_key = access_key
        self.keywords = keywords or ['porcupine']  # За замовчуванням
        self.sensitivities = sensitivities or [0.5] * len(self.keywords)

        self.porcupine = None
        self.audio_stream = None
        self.pa = None

        self._init_porcupine()

    def _init_porcupine(self):
        """Ініціалізувати Porcupine"""
        try:
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=self.keywords,
                sensitivities=self.sensitivities
            )

            self.pa = pyaudio.PyAudio()

            print(f"Wake word detector initialized with keywords: {self.keywords}")
            print(f"Sample rate: {self.porcupine.sample_rate}")
            print(f"Frame length: {self.porcupine.frame_length}")

        except Exception as e:
            print(f"Failed to initialize wake word detector: {e}")
            print("Get your access key from https://console.picovoice.ai/")
            raise

    def start_listening(self, callback: Callable[[int], None]):
        """
        Почати слухати кодове слово

        Args:
            callback: Функція що викликається при детекції (отримує індекс слова)
        """
        if not self.porcupine:
            raise RuntimeError("Porcupine not initialized")

        try:
            # Відкрити аудіо потік
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )

            print("\nListening for wake word...")
            print(f"Say one of: {', '.join(self.keywords)}")

            while True:
                # Читати аудіо фрейм
                pcm = self.audio_stream.read(self.porcupine.frame_length)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)

                # Детектувати wake word
                keyword_index = self.porcupine.process(pcm)

                if keyword_index >= 0:
                    print(f"\n✓ Detected: {self.keywords[keyword_index]}")
                    callback(keyword_index)

        except KeyboardInterrupt:
            print("\nStopping wake word detection...")
        finally:
            self.stop_listening()

    def stop_listening(self):
        """Зупинити прослуховування"""
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()

        if self.porcupine:
            self.porcupine.delete()

        if self.pa:
            self.pa.terminate()

        print("Wake word detector stopped")


# Простий тест модуля
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python wake_word.py <ACCESS_KEY>")
        print("Get your access key from https://console.picovoice.ai/")
        sys.exit(1)

    access_key = sys.argv[1]

    def on_wake_word_detected(keyword_index):
        print(f"Wake word detected! Index: {keyword_index}")
        print("You can now give your command...")

    detector = WakeWordDetector(
        access_key=access_key,
        keywords=['porcupine', 'computer'],  # Доступні безкоштовні слова
        sensitivities=[0.5, 0.5]
    )

    try:
        detector.start_listening(on_wake_word_detected)
    except Exception as e:
        print(f"Error: {e}")
