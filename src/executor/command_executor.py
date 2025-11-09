"""
Command Executor - виконання команд операційної системи
"""
import subprocess
import os
import platform
from typing import Dict, Any


class CommandExecutor:
    """Виконує команди на основі інструкцій від AI"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.apps = config.get("apps", {})
        self.folders = config.get("folders", {})
        self.macros = config.get("macros", {})
        self.is_windows = platform.system() == "Windows"

    def execute(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Виконати команду на основі результату від AI

        Args:
            intent_result: Результат від AI провайдера з полями intent, action

        Returns:
            Dict з результатом виконання: success, message
        """
        intent = intent_result.get("intent")
        action = intent_result.get("action", {})
        action_type = action.get("type")

        # Маршрутизація до відповідного обробника
        handlers = {
            "open_app": self._handle_open_app,
            "switch_app": self._handle_switch_app,
            "hotkey": self._handle_hotkey,
            "volume": self._handle_volume,
            "system_toggle": self._handle_system_toggle,
            "open_folder": self._handle_open_folder,
            "file_search": self._handle_file_search,
            "insert_text": self._handle_insert_text,
            "run_macro": self._handle_run_macro,
            "confirm_required": self._handle_confirm_required,
            "shutdown": self._handle_shutdown,
            "search_request": self._handle_search_request,
            "display_results_summary": self._handle_display_results,
            "none": lambda a: {"success": False, "message": "No action to execute"}
        }

        handler = handlers.get(action_type)
        if handler:
            return handler(action)
        else:
            return {
                "success": False,
                "message": f"Unknown action type: {action_type}"
            }

    def _handle_open_app(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Запустити програму"""
        app_id = action.get("app_id")
        if not app_id or app_id not in self.apps:
            return {"success": False, "message": f"App not found: {app_id}"}

        app_path = self.apps[app_id]

        try:
            if self.is_windows:
                # Windows: використовувати subprocess.Popen
                subprocess.Popen(app_path, shell=True)
            else:
                # Linux/Mac
                subprocess.Popen([app_path])

            return {
                "success": True,
                "message": f"Opened {app_id}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to open {app_id}: {str(e)}"
            }

    def _handle_switch_app(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Переключитись на вікно програми (потребує pywinauto)"""
        # TODO: реалізувати через pywinauto
        return {
            "success": False,
            "message": "switch_app not implemented yet - requires pywinauto"
        }

    def _handle_hotkey(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Натиснути гаряче сполучення клавіш (потребує pyautogui)"""
        # TODO: реалізувати через pyautogui
        keys = action.get("keys", [])
        return {
            "success": False,
            "message": f"hotkey not implemented yet - would press: {keys}"
        }

    def _handle_volume(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Керування гучністю (потребує pycaw на Windows)"""
        # TODO: реалізувати через pycaw
        mode = action.get("mode")
        value = action.get("value", 10)
        return {
            "success": False,
            "message": f"volume control not implemented yet - mode: {mode}, value: {value}"
        }

    def _handle_system_toggle(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Перемикання системних налаштувань"""
        # TODO: реалізувати
        target = action.get("target")
        state = action.get("state")
        return {
            "success": False,
            "message": f"system_toggle not implemented yet - {target}: {state}"
        }

    def _handle_open_folder(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Відкрити папку"""
        folder_id = action.get("folder_id")
        if not folder_id or folder_id not in self.folders:
            return {"success": False, "message": f"Folder not found: {folder_id}"}

        folder_path = self.folders[folder_id]

        try:
            if self.is_windows:
                os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", folder_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", folder_path])

            return {
                "success": True,
                "message": f"Opened folder {folder_id}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to open folder: {str(e)}"
            }

    def _handle_file_search(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Пошук файлів"""
        # TODO: інтеграція з Everything Search API (Windows) або locate (Linux)
        query = action.get("query")
        return {
            "success": False,
            "message": f"file_search not implemented yet - query: {query}"
        }

    def _handle_insert_text(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Вставити текст (потребує pyautogui)"""
        # TODO: реалізувати через pyautogui
        text = action.get("text")
        return {
            "success": False,
            "message": f"insert_text not implemented yet - text: {text[:50]}..."
        }

    def _handle_run_macro(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Запустити макрос (послідовність дій)"""
        macro_id = action.get("macro_id")
        if not macro_id or macro_id not in self.macros:
            return {"success": False, "message": f"Macro not found: {macro_id}"}

        macro = self.macros[macro_id]
        actions = macro.get("actions", [])

        # Виконати всі дії макросу
        results = []
        for macro_action in actions:
            result = self.execute({"intent": "macro_step", "action": macro_action})
            results.append(result)

        # Перевірити чи всі дії виконались успішно
        all_success = all(r.get("success", False) for r in results)

        return {
            "success": all_success,
            "message": f"Macro {macro_id} executed: {len(results)} actions"
        }

    def _handle_confirm_required(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Вимагає підтвердження (для небезпечних операцій)"""
        operation = action.get("operation")
        return {
            "success": True,
            "message": f"Confirmation required for: {operation}",
            "requires_confirmation": True
        }

    def _handle_shutdown(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Вимкнення/перезавантаження системи"""
        mode = action.get("mode", "poweroff")

        # УВАГА: Це реально виконає команду!
        # У production додати додаткові перевірки
        try:
            if self.is_windows:
                if mode == "poweroff":
                    cmd = "shutdown /s /t 5"
                elif mode == "reboot":
                    cmd = "shutdown /r /t 5"
                else:
                    return {"success": False, "message": f"Unknown mode: {mode}"}

                subprocess.Popen(cmd, shell=True)
            else:
                if mode == "poweroff":
                    subprocess.Popen(["shutdown", "-h", "now"])
                elif mode == "reboot":
                    subprocess.Popen(["shutdown", "-r", "now"])

            return {
                "success": True,
                "message": f"System {mode} initiated"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to {mode}: {str(e)}"
            }

    def _handle_search_request(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Пошук в інтернеті або AI запит"""
        # TODO: інтеграція з браузером або API
        provider = action.get("provider")
        query = action.get("query")
        return {
            "success": False,
            "message": f"search_request not implemented yet - {provider}: {query}"
        }

    def _handle_display_results(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Відобразити результати пошуку"""
        # TODO: показати в GUI або консолі
        return {
            "success": True,
            "message": "Results displayed"
        }
