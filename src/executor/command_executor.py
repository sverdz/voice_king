"""
Command Executor - виконання команд операційної системи
"""
import subprocess
import os
import platform
import time
from typing import Dict, Any

# Імпорти для автоматизації (опціональні)
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    from pywinauto import Application
    from pywinauto.findwindows import find_windows
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False

try:
    # Для Windows керування гучністю
    if platform.system() == "Windows":
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        PYCAW_AVAILABLE = True
    else:
        PYCAW_AVAILABLE = False
except ImportError:
    PYCAW_AVAILABLE = False


class CommandExecutor:
    """Виконує команди на основі інструкцій від AI"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.apps = config.get("apps", {})
        self.folders = config.get("folders", {})
        self.macros = config.get("macros", {})
        self.is_windows = platform.system() == "Windows"

        # Ініціалізація volume interface для Windows
        self.volume_interface = None
        if self.is_windows and PYCAW_AVAILABLE:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(
                    IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
            except Exception as e:
                print(f"Warning: Failed to init volume control: {e}")

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
        """Переключитись на вікно програми"""
        if not PYWINAUTO_AVAILABLE:
            return {
                "success": False,
                "message": "pywinauto not installed. Run: pip install pywinauto"
            }

        target = action.get("target", "")
        if not target:
            return {"success": False, "message": "No target window specified"}

        try:
            # Знайти вікна з назвою що містить target
            windows = find_windows(title_re=f".*{target}.*")

            if not windows:
                return {
                    "success": False,
                    "message": f"Window not found: {target}"
                }

            # Активувати перше знайдене вікно
            from pywinauto.application import Application
            app = Application().connect(handle=windows[0])
            app.top_window().set_focus()

            return {
                "success": True,
                "message": f"Switched to window: {target}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to switch window: {str(e)}"
            }

    def _handle_hotkey(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Натиснути гаряче сполучення клавіш"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "message": "pyautogui not installed. Run: pip install pyautogui"
            }

        keys = action.get("keys", [])
        if not keys:
            return {"success": False, "message": "No keys specified"}

        try:
            # Конвертувати ключі в формат pyautogui
            key_mapping = {
                "ctrl": "ctrl",
                "control": "ctrl",
                "alt": "alt",
                "shift": "shift",
                "win": "win",
                "windows": "win",
                "enter": "enter",
                "tab": "tab",
                "esc": "esc",
                "escape": "esc",
                "space": "space",
                "f4": "f4",
                "d": "d",
                "s": "s",
                "c": "c",
                "v": "v",
                "x": "x",
                "z": "z",
                "a": "a"
            }

            mapped_keys = [key_mapping.get(k.lower(), k.lower()) for k in keys]

            # Натиснути комбінацію
            if len(mapped_keys) == 1:
                pyautogui.press(mapped_keys[0])
            else:
                pyautogui.hotkey(*mapped_keys)

            return {
                "success": True,
                "message": f"Pressed: {'+'.join(keys)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to press hotkey: {str(e)}"
            }

    def _handle_volume(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Керування гучністю"""
        if not self.is_windows:
            # Для Linux можна використати amixer
            return self._handle_volume_linux(action)

        if not PYCAW_AVAILABLE or not self.volume_interface:
            return {
                "success": False,
                "message": "pycaw not installed or failed to init. Run: pip install pycaw"
            }

        mode = action.get("mode")
        value = action.get("value", 10)

        try:
            # Отримати поточну гучність (0.0 - 1.0)
            current_volume = self.volume_interface.GetMasterVolumeLevelScalar()

            if mode == "mute":
                # Перемкнути mute
                is_muted = self.volume_interface.GetMute()
                self.volume_interface.SetMute(not is_muted, None)
                return {
                    "success": True,
                    "message": f"Volume {'unmuted' if is_muted else 'muted'}"
                }

            elif mode == "set":
                # Встановити конкретну гучність (value в відсотках)
                new_volume = max(0.0, min(1.0, value / 100.0))
                self.volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
                return {
                    "success": True,
                    "message": f"Volume set to {int(new_volume * 100)}%"
                }

            elif mode == "up":
                # Збільшити гучність
                new_volume = min(1.0, current_volume + (value / 100.0))
                self.volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
                return {
                    "success": True,
                    "message": f"Volume increased to {int(new_volume * 100)}%"
                }

            elif mode == "down":
                # Зменшити гучність
                new_volume = max(0.0, current_volume - (value / 100.0))
                self.volume_interface.SetMasterVolumeLevelScalar(new_volume, None)
                return {
                    "success": True,
                    "message": f"Volume decreased to {int(new_volume * 100)}%"
                }

            else:
                return {
                    "success": False,
                    "message": f"Unknown volume mode: {mode}"
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to control volume: {str(e)}"
            }

    def _handle_volume_linux(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Керування гучністю на Linux через amixer"""
        mode = action.get("mode")
        value = action.get("value", 10)

        try:
            if mode == "mute":
                subprocess.run(["amixer", "set", "Master", "toggle"], check=True)
                return {"success": True, "message": "Volume muted/unmuted"}

            elif mode == "set":
                subprocess.run(["amixer", "set", "Master", f"{value}%"], check=True)
                return {"success": True, "message": f"Volume set to {value}%"}

            elif mode == "up":
                subprocess.run(["amixer", "set", "Master", f"{value}%+"], check=True)
                return {"success": True, "message": f"Volume increased by {value}%"}

            elif mode == "down":
                subprocess.run(["amixer", "set", "Master", f"{value}%-"], check=True)
                return {"success": True, "message": f"Volume decreased by {value}%"}

            else:
                return {"success": False, "message": f"Unknown volume mode: {mode}"}

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to control volume (Linux): {str(e)}"
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
        """Вставити текст"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "success": False,
                "message": "pyautogui not installed. Run: pip install pyautogui"
            }

        text = action.get("text", "")
        if not text:
            return {"success": False, "message": "No text to insert"}

        try:
            # Невелика затримка щоб користувач встиг переключитись на потрібне вікно
            time.sleep(0.3)

            # Вставити текст
            pyautogui.write(text, interval=0.05)

            return {
                "success": True,
                "message": f"Inserted text: {text[:50]}..."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to insert text: {str(e)}"
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
