import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import orchestrator


def build_payload(**overrides):
    payload = {
        "state": "activated",
        "locale": "uk-UA",
        "transcript": "",
        "policies": {
            "allow_run_apps": True,
            "allow_hotkeys": True,
            "allow_audio": True,
            "allow_system_toggle": True,
            "allow_file_ops": True,
            "allow_network_search": True,
            "allow_llm_query": True,
            "allow_llm_summarize": True,
            "dictation": True,
            "tts_max_chars": 120,
        },
        "apps": [],
        "windows": [],
        "folders": [],
        "macros": [],
        "aliases": [],
        "result_set": [],
    }
    payload.update(overrides)
    return payload


def test_run_app_with_alias():
    payload = build_payload(
        transcript="Відкрий ноупад",
        apps=[{"name": "Notepad", "path": "C:/Windows/notepad.exe"}],
        aliases=[{"name": "ноупад", "maps_to": "Notepad"}],
    )
    result = orchestrator.process_request(payload)
    assert result["action"] == "run_app"
    assert result["params"]["app"] == "Notepad"
    assert result["log"]["intent_detected"] == "run_app"


def test_policy_denied_text_input():
    policies = build_payload()["policies"].copy()
    policies["dictation"] = False
    payload = build_payload(
        transcript="Вставити текст: привіт",
        policies=policies,
    )
    result = orchestrator.process_request(payload)
    assert result["action"] == "none"
    assert result["log"]["policy_checks"][0]["status"] == "denied"
    assert "policy_violation" in result["log"]["errors"]


def test_web_search_default_engine():
    payload = build_payload(transcript="Пошук в інтернеті: тест")
    result = orchestrator.process_request(payload)
    assert result["action"] == "web_search"
    assert result["params"]["engine"] == "google"
    assert result["params"]["query"] == "тест"


def test_speak_results_from_summary():
    payload = build_payload(transcript="", llm_summary="Готове резюме")
    result = orchestrator.process_request(payload)
    assert result["action"] == "speak_results"
    assert result["tts"]["say"] == "Готове резюме"


def test_critical_operation_requires_confirmation():
    payload = build_payload(transcript="Вимкни комп'ютер")
    result = orchestrator.process_request(payload)
    assert result["confirmation"]["required"] is True
    assert "Вимкнути комп'ютер" in result["confirmation"]["phrase"]


def test_cli_roundtrip(tmp_path, monkeypatch, capsys):
    payload = build_payload(transcript="Пошук в інтернеті: погода Київ")
    payload_json = json.dumps(payload, ensure_ascii=False)
    input_path = tmp_path / "input.json"
    input_path.write_text(payload_json, encoding="utf-8")

    stdin = input_path.open("r", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    try:
        assert orchestrator.main() == 0
    finally:
        stdin.close()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["action"] == "web_search"
    assert output["params"]["query"] == "погода київ"
