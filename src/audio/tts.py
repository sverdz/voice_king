"""
Text-to-Speech модуль
"""
import pyttsx3
from typing import Optional


class TextToSpeech:
    """Синтез мовлення"""

    def __init__(self, language: str = "uk", rate: int = 150, volume: float = 1.0):
        """
        Ініціалізація TTS

        Args:
            language: Код мови (uk, en, ru)
            rate: Швидкість мовлення (слів за хвилину)
            volume: Гучність (0.0 - 1.0)
        """
        self.language = language
        self.rate = rate
        self.volume = volume
        self.engine = None

        self._init_engine()

    def _init_engine(self):
        """Ініціалізувати TTS движок"""
        try:
            self.engine = pyttsx3.init()

            # Налаштування
            self.engine.setProperty('rate', self.rate)
            self.engine.setProperty('volume', self.volume)

            # Спробувати знайти український голос (якщо є)
            voices = self.engine.getProperty('voices')

            # Для української Windows може бути голос "Microsoft Hanna Desktop"
            # або інші українські голоси
            ukrainian_voice = None
            for voice in voices:
                if 'uk' in voice.languages or 'ukrainian' in voice.name.lower():
                    ukrainian_voice = voice.id
                    break

            if ukrainian_voice:
                self.engine.setProperty('voice', ukrainian_voice)
                print(f"Використовується український голос")
            else:
                print("Український голос не знайдено, використовується голос за замовчуванням")

        except Exception as e:
            print(f"Помилка ініціалізації TTS: {e}")
            self.engine = None

    def speak(self, text: str, block: bool = True):
        """
        Озвучити текст

        Args:
            text: Текст для озвучення
            block: Чекати завершення озвучення (True) або продовжити (False)
        """
        if not self.engine:
            print("TTS не ініціалізований")
            return

        if not text:
            return

        try:
            print(f"TTS: {text}")
            self.engine.say(text)

            if block:
                self.engine.runAndWait()
            else:
                # Non-blocking mode
                self.engine.startLoop(False)
                self.engine.iterate()
                self.engine.endLoop()

        except Exception as e:
            print(f"Помилка озвучення: {e}")

    def set_rate(self, rate: int):
        """Змінити швидкість мовлення"""
        if self.engine:
            self.rate = rate
            self.engine.setProperty('rate', rate)

    def set_volume(self, volume: float):
        """Змінити гучність (0.0 - 1.0)"""
        if self.engine:
            self.volume = max(0.0, min(1.0, volume))
            self.engine.setProperty('volume', self.volume)

    def stop(self):
        """Зупинити озвучення"""
        if self.engine:
            try:
                self.engine.stop()
            except:
                pass


# Простий тест модуля
if __name__ == "__main__":
    tts = TextToSpeech(language="uk")
    tts.speak("Привіт! Я голосовий асистент.")
    tts.speak("Тестую український синтез мовлення.")
