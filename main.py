"""
Voice King - Голосовий асистент для Windows
Головний файл запуску
"""
import sys
import json
from colorama import init, Fore, Style

# Ініціалізація colorama для кольорового виводу
init(autoreset=True)

# Імпорт модулів проекту
from src.config_loader import ConfigLoader
from src.audio import SpeechToText, TextToSpeech, WakeWordDetector
from src.executor import CommandExecutor


class VoiceAssistant:
    """Головний клас голосового асистента"""

    def __init__(self, config_path: str = "config/config.json"):
        """Ініціалізація асистента"""
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}Voice King - Голосовий Асистент")
        print(f"{Fore.CYAN}{'='*60}\n")

        # Завантажити конфігурацію
        print(f"{Fore.YELLOW}Завантаження конфігурації...")
        try:
            self.config = ConfigLoader(config_path)
            print(f"{Fore.GREEN}✓ Конфігурація завантажена")
        except Exception as e:
            print(f"{Fore.RED}✗ Помилка завантаження конфігурації: {e}")
            sys.exit(1)

        # Ініціалізація AI провайдера
        provider_name = self.config.get("ai_provider")
        print(f"{Fore.YELLOW}Ініціалізація AI провайдера: {provider_name}...")
        try:
            self.ai_provider = self.config.get_ai_provider()
            print(f"{Fore.GREEN}✓ AI провайдер готовий")
        except Exception as e:
            print(f"{Fore.RED}✗ Помилка ініціалізації AI: {e}")
            sys.exit(1)

        # Ініціалізація STT (Speech-to-Text)
        audio_config = self.config.get("audio", {})
        stt_model = audio_config.get("stt_model", "base")
        language = self.config.get("language", "uk-UA").split("-")[0]  # uk-UA -> uk

        print(f"{Fore.YELLOW}Завантаження Speech-to-Text моделі ({stt_model})...")
        try:
            self.stt = SpeechToText(model_size=stt_model, language=language)
            print(f"{Fore.GREEN}✓ STT готовий")
        except Exception as e:
            print(f"{Fore.RED}✗ Помилка ініціалізації STT: {e}")
            print(f"{Fore.YELLOW}Асистент працюватиме без розпізнавання мовлення")
            self.stt = None

        # Ініціалізація TTS (Text-to-Speech)
        tts_enabled = self.config.get("tts_enabled", True)
        if tts_enabled:
            print(f"{Fore.YELLOW}Ініціалізація Text-to-Speech...")
            try:
                self.tts = TextToSpeech(language=language)
                print(f"{Fore.GREEN}✓ TTS готовий")
            except Exception as e:
                print(f"{Fore.RED}✗ Помилка ініціалізації TTS: {e}")
                self.tts = None
        else:
            self.tts = None

        # Ініціалізація executor
        print(f"{Fore.YELLOW}Ініціалізація Command Executor...")
        try:
            self.executor = CommandExecutor(self.config.config)
            print(f"{Fore.GREEN}✓ Executor готовий")
        except Exception as e:
            print(f"{Fore.RED}✗ Помилка ініціалізації Executor: {e}")
            sys.exit(1)

        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}Асистент готовий до роботи!")
        print(f"{Fore.GREEN}{'='*60}\n")

    def process_command(self, command_text: str) -> dict:
        """
        Обробити голосову команду

        Args:
            command_text: Текст команди

        Returns:
            Результат виконання
        """
        print(f"{Fore.CYAN}► Команда: {command_text}")

        # Отримати намір від AI
        context = self.config.get_context()
        intent_result = self.ai_provider.get_intent(command_text, context)

        print(f"{Fore.MAGENTA}► AI відповідь:")
        print(f"  Intent: {intent_result.get('intent')}")
        print(f"  Action: {json.dumps(intent_result.get('action'), ensure_ascii=False)}")

        if "error" in intent_result:
            print(f"{Fore.RED}  Error: {intent_result['error']}")

        # Виконати команду
        if intent_result.get("intent") != "unknown":
            execution_result = self.executor.execute(intent_result)

            print(f"{Fore.YELLOW}► Виконання:")
            print(f"  Success: {execution_result.get('success')}")
            print(f"  Message: {execution_result['message']}")

            # Озвучити результат якщо є
            if self.tts and "speech" in intent_result:
                speech_text = intent_result["speech"]
                print(f"{Fore.GREEN}► Озвучення: {speech_text}")
                self.tts.speak(speech_text)

            return execution_result
        else:
            error_msg = intent_result.get("error", "Команду не розпізнано")
            print(f"{Fore.RED}► Помилка: {error_msg}")

            if self.tts and "speech" in intent_result:
                self.tts.speak(intent_result["speech"])

            return {"success": False, "message": error_msg}

    def run_interactive(self):
        """Запустити в інтерактивному режимі (текстовий ввід)"""
        print(f"{Fore.CYAN}Режим: Текстовий ввід")
        print(f"{Fore.YELLOW}Введіть команду або 'exit' для виходу\n")

        while True:
            try:
                command = input(f"{Fore.GREEN}Ви: {Style.RESET_ALL}")

                if command.lower() in ['exit', 'quit', 'вихід']:
                    print(f"{Fore.CYAN}До побачення!")
                    break

                if command.strip():
                    self.process_command(command)
                    print()

            except KeyboardInterrupt:
                print(f"\n{Fore.CYAN}До побачення!")
                break
            except Exception as e:
                print(f"{Fore.RED}Помилка: {e}")

    def run_voice(self, duration: int = 5):
        """Запустити в голосовому режимі"""
        if not self.stt:
            print(f"{Fore.RED}STT не ініціалізований. Використовуйте текстовий режим.")
            return

        print(f"{Fore.CYAN}Режим: Голосовий ввід")
        print(f"{Fore.YELLOW}Натисніть Enter для запису команди або 'exit' для виходу\n")

        while True:
            try:
                user_input = input(f"{Fore.GREEN}Натисніть Enter для запису (або 'exit'): {Style.RESET_ALL}")

                if user_input.lower() in ['exit', 'quit', 'вихід']:
                    print(f"{Fore.CYAN}До побачення!")
                    break

                print(f"{Fore.YELLOW}Слухаю... ({duration} сек)")
                command_text = self.stt.listen_and_transcribe(duration=duration)

                if command_text:
                    self.process_command(command_text)
                else:
                    print(f"{Fore.RED}Не вдалося розпізнати мовлення")

                print()

            except KeyboardInterrupt:
                print(f"\n{Fore.CYAN}До побачення!")
                break
            except Exception as e:
                print(f"{Fore.RED}Помилка: {e}")

    def run_wake_word_mode(self, access_key: str, duration: int = 5):
        """
        Запустити в режимі з wake word detection

        Args:
            access_key: Picovoice access key
            duration: Тривалість запису після детекції wake word
        """
        if not self.stt:
            print(f"{Fore.RED}STT не ініціалізований.")
            return

        print(f"{Fore.CYAN}Режим: Wake Word Detection")
        print(f"{Fore.YELLOW}Ініціалізація детектора кодового слова...\n")

        try:
            # Отримати wake word з конфігу або використати за замовчуванням
            audio_config = self.config.get("audio", {})
            wake_words = audio_config.get("wake_words", ["porcupine"])

            detector = WakeWordDetector(
                access_key=access_key,
                keywords=wake_words,
                sensitivities=[0.5] * len(wake_words)
            )

            def on_wake_word(keyword_index):
                """Callback при детекції wake word"""
                print(f"{Fore.GREEN}\n🎤 Слухаю команду... ({duration} сек)")

                if self.tts:
                    self.tts.speak("Слухаю", block=False)

                # Записати команду
                command_text = self.stt.listen_and_transcribe(duration=duration)

                if command_text:
                    self.process_command(command_text)
                else:
                    print(f"{Fore.RED}Не вдалося розпізнати команду")
                    if self.tts:
                        self.tts.speak("Не розумію")

                print(f"{Fore.CYAN}\nОчікую кодове слово...\n")

            # Запустити детектор
            detector.start_listening(on_wake_word)

        except KeyboardInterrupt:
            print(f"\n{Fore.CYAN}До побачення!")
        except Exception as e:
            print(f"{Fore.RED}Помилка wake word detection: {e}")
            print(f"{Fore.YELLOW}Переконайтесь що у вас є access key від Picovoice")
            print(f"{Fore.YELLOW}Отримати можна на: https://console.picovoice.ai/")


def main():
    """Головна функція"""
    # Перевірити аргументи командного рядка
    mode = "text"  # За замовчуванням текстовий режим
    wake_word_key = None

    if len(sys.argv) > 1:
        if sys.argv[1] in ["--voice", "-v"]:
            mode = "voice"
        elif sys.argv[1] in ["--wake-word", "-w"]:
            mode = "wake_word"
            if len(sys.argv) > 2:
                wake_word_key = sys.argv[2]
            else:
                print(f"{Fore.RED}Error: --wake-word requires Picovoice access key")
                print(f"{Fore.YELLOW}Usage: python main.py --wake-word YOUR_ACCESS_KEY")
                print(f"{Fore.YELLOW}Get key from: https://console.picovoice.ai/")
                sys.exit(1)
        elif sys.argv[1] in ["--help", "-h"]:
            print("Voice King - Голосовий Асистент")
            print("\nВикористання:")
            print("  python main.py                          - Текстовий режим")
            print("  python main.py --voice                  - Голосовий режим (кнопка)")
            print("  python main.py --wake-word <ACCESS_KEY> - Режим з wake word")
            print("  python main.py --help                   - Ця довідка")
            print("\nПриклади:")
            print("  python main.py")
            print("  python main.py --voice")
            print("  python main.py --wake-word sk-xxxxx")
            return

    # Створити та запустити асистента
    try:
        assistant = VoiceAssistant()

        if mode == "wake_word":
            assistant.run_wake_word_mode(access_key=wake_word_key, duration=5)
        elif mode == "voice":
            assistant.run_voice(duration=5)
        else:
            assistant.run_interactive()

    except Exception as e:
        print(f"{Fore.RED}Критична помилка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
