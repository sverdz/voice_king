"""Voice King Orchestrator reference implementation.

This module implements the deterministic command orchestrator described in the
repository README.  The entry point is :func:`process_request`, which expects a
single dictionary payload that mirrors the JSON contract exchanged with the
backend.  A small CLI wrapper is provided so the orchestrator can be used from
scripts or manual tests by piping JSON through standard input.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_ACTIONS = {
    "run_app",
    "focus_window",
    "hotkey",
    "audio_control",
    "system_toggle",
    "open_folder",
    "file_search",
    "file_list",
    "mkdir_here",
    "open_recent",
    "text_input",
    "web_search",
    "speak_results",
    "run_macro",
    "llm_query",
    "llm_summarize",
    "none",
}


@dataclass
class PolicyGate:
    name: str
    allowed: bool
    deny_action: str


def _base_response() -> Dict[str, Any]:
    """Return the canonical empty response template."""

    return {
        "action": "none",
        "params": {},
        "confirmation": {"required": False, "phrase": ""},
        "tts": {"say": "", "display": ""},
        "log": {
            "intent_detected": "",
            "confidence": 0.0,
            "slots": {},
            "policy_checks": [],
            "resolution": {},
            "errors": [],
        },
        "need_more_info": "",
    }


def _apply_tts_limit(text: str, max_chars: Optional[int]) -> str:
    if max_chars is None or len(text) <= max_chars:
        return text
    truncated = text[: max_chars - 1].rstrip()
    return truncated + "…"


def _resolve_dict(entries: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    name_lower = name.lower()
    for entry in entries:
        for key in ("name", "title", "label"):
            value = entry.get(key)
            if value and value.lower() == name_lower:
                return entry
    return None


def _match_alias(aliases: List[Dict[str, Any]], spoken: str) -> Optional[str]:
    spoken_lower = spoken.lower()
    for alias in aliases:
        name = alias.get("name")
        target = alias.get("maps_to")
        if name and target and name.lower() == spoken_lower:
            return target
    return None


def _policy_gate_checks(action: str, policies: Dict[str, Any]) -> List[PolicyGate]:
    mapping = {
        "run_app": PolicyGate("allow_run_apps", True, "policy_violation"),
        "focus_window": PolicyGate("allow_run_apps", True, "policy_violation"),
        "hotkey": PolicyGate("allow_hotkeys", True, "policy_violation"),
        "audio_control": PolicyGate("allow_audio", True, "policy_violation"),
        "system_toggle": PolicyGate("allow_system_toggle", True, "policy_violation"),
        "open_folder": PolicyGate("allow_file_ops", True, "policy_violation"),
        "file_search": PolicyGate("allow_file_ops", True, "policy_violation"),
        "file_list": PolicyGate("allow_file_ops", True, "policy_violation"),
        "mkdir_here": PolicyGate("allow_file_ops", True, "policy_violation"),
        "open_recent": PolicyGate("allow_file_ops", True, "policy_violation"),
        "text_input": PolicyGate("dictation", True, "policy_violation"),
        "web_search": PolicyGate("allow_network_search", True, "policy_violation"),
        "llm_query": PolicyGate("allow_llm_query", True, "policy_violation"),
        "llm_summarize": PolicyGate("allow_llm_summarize", True, "policy_violation"),
    }

    gate = mapping.get(action)
    if not gate:
        return []

    allowed = bool(policies.get(gate.name, False))
    return [PolicyGate(gate.name, allowed, gate.deny_action)]


def _set_policy_checks(response: Dict[str, Any], gates: List[PolicyGate]) -> None:
    checks = []
    for gate in gates:
        status = "granted" if gate.allowed else "denied"
        checks.append({"policy": gate.name, "status": status})
    response["log"]["policy_checks"] = checks


def _deny_for_policy(response: Dict[str, Any], gates: List[PolicyGate]) -> bool:
    for gate in gates:
        if not gate.allowed:
            response["action"] = "none"
            response["params"] = {}
            response["log"]["errors"].append(gate.deny_action)
            response["log"]["resolution"] = {"denied_policy": gate.name}
            return True
    return False


def _make_confirmation(response: Dict[str, Any], phrase: str) -> None:
    response["confirmation"] = {"required": True, "phrase": phrase}


def process_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single orchestrator request."""

    response = _base_response()

    policies = payload.get("policies", {}) or {}
    tts_max = payload.get("policies", {}).get("tts_max_chars") if policies else None

    state = payload.get("state", "passive")
    transcript = (payload.get("transcript") or "").strip()
    locale = payload.get("locale", "uk-UA")
    result_set = payload.get("result_set") or []
    llm_summary = payload.get("llm_summary")

    if state != "activated":
        response["tts"]["say"] = _apply_tts_limit(
            "Активуйте мене кодовою фразою, щоб виконати команду.", tts_max
        )
        response["log"]["intent_detected"] = "idle"
        response["log"]["confidence"] = 1.0
        return response

    if llm_summary and not transcript:
        response["action"] = "speak_results"
        response["params"] = {"source": "llm_summary"}
        response["tts"]["say"] = _apply_tts_limit(str(llm_summary), tts_max)
        response["log"]["intent_detected"] = "speak_results"
        response["log"]["confidence"] = 1.0
        response["log"]["resolution"] = {"source": "llm_summary"}
        return response

    normalized = transcript.lower()

    prechecked = _run_intents(normalized, payload)
    if prechecked:
        response.update(prechecked.response)
        response["log"]["intent_detected"] = "critical"
        response["log"]["confidence"] = prechecked.confidence
        response["log"]["slots"] = prechecked.slots
        if prechecked.resolution:
            response["log"]["resolution"] = prechecked.resolution
        response["tts"]["say"] = _apply_tts_limit(prechecked.tts, tts_max)
        return response

    if not transcript:
        response["need_more_info"] = "Потрібна голосова команда."
        response["log"]["intent_detected"] = "missing_transcript"
        response["log"]["confidence"] = 0.1
        return response
    

    apps = payload.get("apps", []) or []
    windows = payload.get("windows", []) or []
    folders = payload.get("folders", []) or []
    macros = payload.get("macros", []) or []
    aliases = payload.get("aliases", []) or []

    # Command detection
    intent_handlers: List[Tuple[str, Any]] = [
        ("run_app", _handle_run_app),
        ("focus_window", _handle_focus_window),
        ("hotkey", _handle_hotkey),
        ("audio_control", _handle_audio_control),
        ("system_toggle", _handle_system_toggle),
        ("open_folder", _handle_open_folder),
        ("file_search", _handle_file_search),
        ("file_list", _handle_file_list),
        ("mkdir_here", _handle_mkdir_here),
        ("open_recent", _handle_open_recent),
        ("text_input", _handle_text_input),
        ("web_search", _handle_web_search),
        ("speak_results", _handle_speak_results),
        ("run_macro", _handle_run_macro),
        ("llm_summarize", _handle_llm_summarize),
        ("llm_query", _handle_llm_query),
    ]

    for intent, handler in intent_handlers:
        result = handler(
            normalized,
            payload,
            apps=apps,
            windows=windows,
            folders=folders,
            macros=macros,
            aliases=aliases,
            result_set=result_set,
        )
        if result:
            response.update(result.response)
            response["log"]["intent_detected"] = intent
            response["log"]["confidence"] = result.confidence
            response["log"]["slots"] = result.slots
            if result.resolution:
                response["log"]["resolution"] = result.resolution

            gates = _policy_gate_checks(response["action"], policies)
            _set_policy_checks(response, gates)
            if _deny_for_policy(response, gates):
                response["tts"]["say"] = _apply_tts_limit(
                    "Цю дію заборонено політиками.", tts_max
                )
            else:
                response["tts"]["say"] = _apply_tts_limit(
                    result.tts or response["tts"].get("say", ""), tts_max
                )
            return response

    response["tts"]["say"] = _apply_tts_limit(
        "Не розпізнала команду. Спробуйте інакше сформулювати запит.", tts_max
    )
    response["log"]["intent_detected"] = "unknown"
    response["log"]["confidence"] = 0.2
    response["log"]["errors"].append("intent_not_found")
    return response


@dataclass
class IntentResult:
    response: Dict[str, Any]
    confidence: float
    slots: Dict[str, Any]
    tts: str = ""
    resolution: Optional[Dict[str, Any]] = None


def _intent_response(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action": action,
        "params": params,
        "confirmation": {"required": False, "phrase": ""},
        "tts": {"say": "", "display": ""},
        "log": {
            "intent_detected": "",
            "confidence": 0.0,
            "slots": {},
            "policy_checks": [],
            "resolution": {},
            "errors": [],
        },
        "need_more_info": "",
    }


def _handle_run_app(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"\b(відкрий|запусти)\s+(.+)", transcript)
    if not match:
        return None

    spoken = match.group(2).strip()
    aliases = kwargs.get("aliases", [])
    apps = kwargs.get("apps", [])

    target_name = _match_alias(aliases, spoken) or spoken
    app = _resolve_dict(apps, target_name)

    if not app:
        response = _intent_response("none", {})
        response["need_more_info"] = "Не знайшла додаток. Уточніть назву."
        return IntentResult(response, 0.4, {"app": spoken}, tts="Не знайшла такого додатка.")

    params = {
        "app": app.get("name", target_name),
        "path": app.get("path"),
    }
    resolution = {"app_id": app.get("id"), "spoken": spoken}
    response = _intent_response("run_app", params)
    tts = f"Запускаю {params['app']}."
    return IntentResult(response, 0.85, {"app": params["app"]}, tts=tts, resolution=resolution)


def _handle_focus_window(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"\b(перемкнись|переключись|перейди)\s+на\s+(.+)", transcript)
    if not match:
        return None

    spoken = match.group(2).strip()
    windows = kwargs.get("windows", [])
    target = _resolve_dict(windows, spoken)

    if not target:
        response = _intent_response("none", {})
        response["need_more_info"] = "Не знайшла вікно. Уточніть назву."
        return IntentResult(response, 0.4, {"window": spoken}, tts="Не знайшла такого вікна.")

    params = {"window": target.get("name", spoken), "id": target.get("id")}
    resolution = {"window_id": target.get("id"), "spoken": spoken}
    response = _intent_response("focus_window", params)
    tts = f"Перемикаюся на {params['window']}."
    return IntentResult(response, 0.8, {"window": params["window"]}, tts=tts, resolution=resolution)


def _handle_hotkey(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    if "закрий вікно" in transcript:
        params = {"keys": ["alt", "f4"]}
        response = _intent_response("hotkey", params)
        tts = "Закриваю активне вікно."
        return IntentResult(response, 0.9, {"keys": "Alt+F4"}, tts=tts)

    if "згорни всі вікна" in transcript or "робочий стіл" in transcript:
        params = {"keys": ["win", "d"]}
        response = _intent_response("hotkey", params)
        tts = "Показую робочий стіл."
        return IntentResult(response, 0.9, {"keys": "Win+D"}, tts=tts)

    match = re.search(r"натисн(и|ути)\s+([a-zа-я0-9+\s]+)", transcript)
    if match:
        combo = match.group(2)
        keys = [k.strip().lower() for k in re.split(r"[+ ]", combo) if k.strip()]
        if not keys:
            return None
        params = {"keys": keys}
        response = _intent_response("hotkey", params)
        tts = "Натискаю комбінацію клавіш."
        return IntentResult(response, 0.7, {"keys": "+".join(k.title() for k in keys)}, tts=tts)

    return None


def _handle_audio_control(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    if "вимкни звук" in transcript or "без звуку" in transcript:
        params = {"operation": "mute"}
        response = _intent_response("audio_control", params)
        tts = "Вимикаю звук."
        return IntentResult(response, 0.9, {}, tts=tts)

    match = re.search(r"(гучніше|тихіше)\s+на\s+(\d+)%", transcript)
    if match:
        direction = match.group(1)
        value = int(match.group(2))
        params = {
            "operation": "volume_up" if direction == "гучніше" else "volume_down",
            "amount": value,
        }
        response = _intent_response("audio_control", params)
        tts = f"Регулюю гучність на {value}%"
        return IntentResult(response, 0.85, {"amount": value, "direction": direction}, tts=tts)

    return None


def _handle_system_toggle(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    toggles = {
        "wi-fi": "wifi",
        "вайфай": "wifi",
        "bluetooth": "bluetooth",
        "режим польоту": "airplane_mode",
    }
    for phrase, feature in toggles.items():
        if f"увімкни {phrase}" in transcript:
            params = {"feature": feature, "state": "on"}
        elif f"вимкни {phrase}" in transcript:
            params = {"feature": feature, "state": "off"}
        else:
            continue
        response = _intent_response("system_toggle", params)
        tts = f"Перемикаю {phrase}."
        return IntentResult(response, 0.85, {"feature": feature, "state": params["state"]}, tts=tts)
    return None


def _handle_open_folder(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"відкрий папку\s+(.+)", transcript)
    if not match:
        return None

    spoken = match.group(1).strip()
    folders = kwargs.get("folders", [])
    folder = _resolve_dict(folders, spoken)
    if not folder:
        response = _intent_response("none", {})
        response["need_more_info"] = "Не знайшла папку. Уточніть назву."
        return IntentResult(response, 0.4, {"folder": spoken}, tts="Не знайшла таку папку.")

    params = {"path": folder.get("path"), "name": folder.get("name", spoken)}
    response = _intent_response("open_folder", params)
    resolution = {"folder_path": folder.get("path"), "spoken": spoken}
    tts = f"Відкриваю папку {params['name']}."
    return IntentResult(response, 0.8, {"folder": params["name"]}, tts=tts, resolution=resolution)


def _handle_file_search(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"знайди файл\s+(.+)", transcript)
    if not match:
        return None
    query = match.group(1).strip()
    params = {"query": query}
    response = _intent_response("file_search", params)
    tts = f"Шукаю файли за запитом {query}."
    return IntentResult(response, 0.75, {"query": query}, tts=tts)


def _handle_file_list(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    if "покажи файли за сьогодні" in transcript:
        params = {"time_filter": "today"}
    elif "покажи файли за вчора" in transcript:
        params = {"time_filter": "yesterday"}
    else:
        match = re.search(r"покажи файли за останні\s+(\d+)\s+дні", transcript)
        if not match:
            return None
        params = {"time_filter": "last_n_days", "days": int(match.group(1))}
    response = _intent_response("file_list", params)
    tts = "Показую відповідні файли."
    return IntentResult(response, 0.7, params, tts=tts)


def _handle_mkdir_here(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"створи папку\s+(.+)\s+тут", transcript)
    if not match:
        return None
    folder_name = match.group(1).strip()
    params = {"name": folder_name}
    response = _intent_response("mkdir_here", params)
    tts = f"Створюю папку {folder_name}."
    return IntentResult(response, 0.75, {"folder": folder_name}, tts=tts)


def _handle_open_recent(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    if "відкрий останній файл" not in transcript:
        return None
    response = _intent_response("open_recent", {})
    tts = "Відкриваю останній файл."
    return IntentResult(response, 0.7, {}, tts=tts)


def _handle_text_input(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"встав(ити|и) текст:?\s+(.+)", transcript)
    if not match:
        return None
    text = match.group(2).strip()
    params = {"text": text}
    response = _intent_response("text_input", params)
    tts = "Вставляю текст."
    return IntentResult(response, 0.75, {"text": text}, tts=tts)


def _handle_web_search(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"(пошук|знайди)\s+(в інтернеті:|в інтернеті|:)\s*(.+)", transcript)
    if match:
        query = match.group(3).strip()
    elif transcript.startswith("пошук "):
        query = transcript.split("пошук ", 1)[1].strip()
    else:
        return None

    engine = payload.get("default_search_engine", "google")
    params = {"engine": engine, "query": query}
    response = _intent_response("web_search", params)
    tts = "Запускаю пошук."
    return IntentResult(response, 0.8, {"query": query}, tts=tts)


def _handle_speak_results(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    if "озвуч результати" not in transcript and "прочитай результати" not in transcript:
        return None

    result_set = kwargs.get("result_set", [])
    if not result_set:
        response = _intent_response("none", {})
        response["need_more_info"] = "Немає результатів для озвучення."
        return IntentResult(response, 0.4, {}, tts="Результати недоступні.")

    snippet = _summarize_result_set(result_set)
    response = _intent_response("speak_results", {"source": "result_set"})
    response["tts"]["say"] = snippet
    return IntentResult(response, 0.8, {"items": len(result_set)}, tts=snippet)


def _summarize_result_set(result_set: List[Dict[str, Any]]) -> str:
    top_items = []
    for item in result_set[:3]:
        title = item.get("title") or item.get("name")
        if not title:
            continue
        summary = item.get("snippet") or item.get("summary")
        if summary:
            top_items.append(f"{title}: {summary}")
        else:
            top_items.append(title)
    if not top_items:
        return "Результати без опису."
    return "; ".join(top_items)


def _handle_run_macro(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    match = re.search(r"увімкн(и|ути) режим\s+(.+)", transcript)
    if not match:
        return None

    spoken = match.group(2).strip()
    macros = kwargs.get("macros", [])
    macro = _resolve_dict(macros, spoken)
    if not macro:
        response = _intent_response("none", {})
        response["need_more_info"] = "Не знайшла макрос. Уточніть назву."
        return IntentResult(response, 0.4, {"macro": spoken}, tts="Не знайшла такий режим.")

    params = {"macro_id": macro.get("id"), "name": macro.get("name", spoken)}
    response = _intent_response("run_macro", params)
    resolution = {"macro_id": macro.get("id"), "spoken": spoken}
    tts = f"Активую режим {params['name']}."
    return IntentResult(response, 0.8, {"macro": params["name"]}, tts=tts, resolution=resolution)


def _handle_llm_summarize(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    if "узагальни" not in transcript and "підсумуй" not in transcript:
        return None

    if not kwargs.get("result_set"):
        response = _intent_response("none", {})
        response["need_more_info"] = "Немає результатів для узагальнення."
        return IntentResult(response, 0.4, {}, tts="Потрібні результати пошуку.")

    params = {
        "source": "web_search",
        "max_sentences": 3,
        "style": "concise_voice_output",
        "context_keys": ["result_set"],
    }
    response = _intent_response("llm_summarize", params)
    resolution = {"llm_context": "result_set"}
    tts = "Передаю результати для узагальнення."
    return IntentResult(response, 0.8, {}, tts=tts, resolution=resolution)


def _handle_llm_query(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    patterns = [r"поясни\s+(.+)", r"що таке\s+(.+)", r"розкажи\s+про\s+(.+)"]
    for pattern in patterns:
        match = re.search(pattern, transcript)
        if not match:
            continue
        topic = match.group(1).strip()
        params = {
            "prompt": (
                "Стисло та зрозуміло поясни наступне українською мовою. "
                "Не вигадуй фактів і дотримуйся тону для голосового озвучення.\n"
                f"Тема: {topic}"
            )
        }
        response = _intent_response("llm_query", params)
        resolution = {"topic": topic}
        tts = "Запитую пояснення у мовної моделі."
        return IntentResult(response, 0.75, {"topic": topic}, tts=tts, resolution=resolution)

    return None


def _handle_critical(transcript: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    if "вимкни комп'ютер" in transcript:
        return "shutdown", "Вимкнути комп'ютер?", {"operation": "shutdown"}
    if "перезавантаж" in transcript:
        return "restart", "Перезавантажити комп'ютер?", {"operation": "restart"}
    if "видали файл" in transcript:
        match = re.search(r"видали файл\s+(.+)", transcript)
        if match:
            filename = match.group(1).strip()
            return "delete_file", f"Видалити файл {filename}?", {"file": filename}
    return None


def _handle_critical_wrapper(transcript: str) -> Optional[IntentResult]:
    critical = _handle_critical(transcript)
    if not critical:
        return None
    intent, phrase, params = critical
    response = _intent_response("none", params)
    _make_confirmation(response, phrase)
    tts = "Потрібне підтвердження."
    return IntentResult(response, 0.8, params, tts=tts, resolution={"critical_intent": intent})


# Extend handler list with critical check at a higher priority
INTENT_PRECHECKS = [_handle_critical_wrapper]


def _run_intents(transcript: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[IntentResult]:
    for handler in INTENT_PRECHECKS:
        result = handler(transcript)
        if result:
            return result
    return None


def main() -> int:
    if sys.stdin.isatty():
        print("Очікую JSON у стандартному вводі.", file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"Помилка читання JSON: {exc}", file=sys.stderr)
        return 2

    result_dict = process_request(payload)
    json.dump(result_dict, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
