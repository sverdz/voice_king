"""
OpenAI Provider - використовує OpenAI API (ChatGPT)
"""
import json
from typing import Dict, Any
from openai import OpenAI
from .base import AIProvider


class OpenAIProvider(AIProvider):
    """Провайдер для OpenAI (ChatGPT)"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", system_prompt: str = ""):
        super().__init__(api_key, model)
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = system_prompt

    def format_input(self, command_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Форматувати вхідні дані для OpenAI"""
        input_data = {
            "text": command_text,
            "apps": context.get("apps", {}),
            "folders": context.get("folders", {}),
            "search_providers": context.get("search_providers", {}),
            "tts_enabled": context.get("tts_enabled", True)
        }

        # Додати опціональні поля якщо є
        if "macros" in context:
            input_data["macros"] = context["macros"]

        return input_data

    def get_intent(self, command_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Отримати намір через OpenAI API"""
        try:
            # Форматувати вхідні дані
            input_data = self.format_input(command_text, context)

            # Створити повідомлення для OpenAI
            user_message = f"Обробити команду: {json.dumps(input_data, ensure_ascii=False)}"

            # Викликати OpenAI API з JSON mode
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                response_format={"type": "json_object"},  # Гарантує JSON відповідь
                max_tokens=1024,
                temperature=0.3  # Нижча температура для детермінованості
            )

            # Витягти JSON відповідь
            response_text = response.choices[0].message.content
            result = json.loads(response_text)

            # Перевірити формат
            if not self.validate_response(result):
                return {
                    "intent": "unknown",
                    "action": {"type": "none"},
                    "error": "INVALID_AI_RESPONSE"
                }

            return result

        except Exception as e:
            return {
                "intent": "unknown",
                "action": {"type": "none"},
                "error": f"AI_ERROR: {str(e)}"
            }
