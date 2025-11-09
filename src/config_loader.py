"""
Config Loader - завантаження та валідація конфігурації
"""
import json
import os
from typing import Dict, Any
from pathlib import Path


class ConfigLoader:
    """Клас для завантаження та управління конфігурацією"""

    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self.config = {}
        self.system_prompt = ""
        self._load_config()
        self._load_system_prompt()

    def _load_config(self):
        """Завантажити конфігурацію з файлу"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Файл конфігурації не знайдено: {self.config_path}\n"
                f"Створіть config/config.json на основі config/config.example.json"
            )

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # Валідація обов'язкових полів
        self._validate_config()

    def _load_system_prompt(self):
        """Завантажити system prompt"""
        prompt_path = "config/system_prompt.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self.system_prompt = f.read().strip()
        else:
            # Базовий промпт якщо файл не знайдено
            self.system_prompt = "Ти голосовий асистент. Повертай тільки JSON з полями: intent, action, speech (опціонально)."

    def _validate_config(self):
        """Перевірити що конфігурація містить необхідні поля"""
        required_fields = ["ai_provider", "apps", "folders"]

        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Обов'язкове поле відсутнє в конфігурації: {field}")

        # Перевірити що вибраний AI провайдер налаштований
        provider = self.config["ai_provider"]
        if provider not in ["claude", "openai"]:
            raise ValueError(f"Невідомий AI провайдер: {provider}. Доступні: claude, openai")

        if provider not in self.config:
            raise ValueError(f"Конфігурація для {provider} відсутня")

        if "api_key" not in self.config[provider]:
            raise ValueError(f"API ключ для {provider} не вказаний")

    def get_ai_provider(self):
        """Отримати налаштований AI провайдер"""
        from .ai_providers import ClaudeProvider, OpenAIProvider

        provider_name = self.config["ai_provider"]
        provider_config = self.config[provider_name]

        if provider_name == "claude":
            return ClaudeProvider(
                api_key=provider_config["api_key"],
                model=provider_config.get("model", "claude-3-haiku-20240307"),
                system_prompt=self.system_prompt
            )
        elif provider_name == "openai":
            return OpenAIProvider(
                api_key=provider_config["api_key"],
                model=provider_config.get("model", "gpt-4o-mini"),
                system_prompt=self.system_prompt
            )

    def get_context(self) -> Dict[str, Any]:
        """
        Отримати контекст для передачі в AI
        (apps, folders, macros, тощо)
        """
        return {
            "apps": self.config.get("apps", {}),
            "folders": self.config.get("folders", {}),
            "search_providers": self.config.get("search_providers", {}),
            "macros": self.config.get("macros", {}),
            "tts_enabled": self.config.get("tts_enabled", True)
        }

    def get(self, key: str, default=None):
        """Отримати значення з конфігурації"""
        return self.config.get(key, default)
