"""
Claude AI Provider - використовує Anthropic API
"""
import json
from typing import Dict, Any
from anthropic import Anthropic
from .base import AIProvider


class ClaudeProvider(AIProvider):
    """Провайдер для Claude AI"""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307", system_prompt: str = ""):
        super().__init__(api_key, model)
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = system_prompt

    def format_input(self, command_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Форматувати вхідні дані для Claude"""
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
        """Отримати намір через Claude API"""
        try:
            # Форматувати вхідні дані
            input_data = self.format_input(command_text, context)

            # Створити повідомлення для Claude
            user_message = f"Обробити команду: {json.dumps(input_data, ensure_ascii=False)}"

            # Викликати Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )

            # Витягти текст відповіді
            response_text = response.content[0].text

            # Спробувати знайти JSON в відповіді
            result = self._extract_json(response_text)

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

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Витягти JSON з тексту відповіді
        Claude може повернути JSON в markdown блоці або просто текстом
        """
        # Спробувати парсити весь текст як JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Шукати JSON в markdown блоці ```json ... ```
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_text = text[start:end].strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass

        # Шукати JSON в звичайному блоці ``` ... ```
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_text = text[start:end].strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass

        # Якщо не знайдено валідний JSON
        raise ValueError(f"Не вдалося витягти JSON з відповіді: {text[:100]}...")
