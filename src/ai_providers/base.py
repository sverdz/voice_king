"""
Базовий клас для AI провайдерів
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class AIProvider(ABC):
    """Абстрактний базовий клас для AI провайдерів"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def get_intent(self, command_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Отримати намір з команди користувача

        Args:
            command_text: Розпізнана голосова команда
            context: Контекст (apps, folders, macros, тощо)

        Returns:
            Dict з полями: intent, action, speech (опціонально), error (опціонально)
        """
        pass

    @abstractmethod
    def format_input(self, command_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Форматувати вхідні дані для AI провайдера

        Args:
            command_text: Розпізнана команда
            context: Контекст виконання

        Returns:
            Сформований об'єкт для відправки до AI
        """
        pass

    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Перевірити чи відповідь має правильний формат

        Args:
            response: Відповідь від AI

        Returns:
            True якщо формат правильний
        """
        required_fields = ["intent", "action"]
        return all(field in response for field in required_fields)
