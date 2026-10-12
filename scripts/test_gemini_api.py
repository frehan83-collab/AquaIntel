"""
Script to test the Gemini API with the loaded Google AI Studio credentials.
Tests model listing, text generation, streaming, and tool/structured responses.
"""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

def _load_api_key() -> str:
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv("GEMINI_API_KEY")
    providers_file = Path.home() / ".cline" / "data" / "settings" / "providers.json"
    if providers_file.exists():
        try:
            with open(providers_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("providers", {}).get("gemini", {}).get("settings", {}).get("apiKey", "")
        except Exception:
            pass
    return ""

API_KEY = _load_api_key()
if not API_KEY:
    raise SystemExit(
        "No Gemini API key found. Set GEMINI_API_KEY (recommended) or ensure the "
        "Cline providers.json contains a gemini apiKey. Refusing to run unauthenticated."
    )
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def list_models():
    url = f"{BASE_URL}/models?key={API_KEY}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        return [m for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]


def test_tool_calling(model_name: str = "gemini-3.8-flash"):
    clean_name = model_name if model_name.startswith("models/") else f"models/{model_name}"
    url = f"{BASE_URL}/{clean_name}:generateContent?key={API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "What is the current salmon spot price for production area 3?"}
                ]
            }
        ],
        "tools": [
            {
                "functionDeclarations": [
                    {
                        "name": "get_salmon_price",
                        "description": "Fetch current salmon spot price by production area",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "production_area": {
                                    "type": "INTEGER",
                                    "description": "Norwegian production area (1-13)"
                                }
                            },
                            "required": ["production_area"]
                        }
                    }
                ]
            }
        ]
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        duration = time.perf_counter() - t0
        res = json.loads(resp.read().decode("utf-8"))
        candidate = res.get("candidates", [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        tool_calls = [p.get("functionCall") for p in parts if "functionCall" in p]
        return {
            "model": clean_name,
            "status": resp.status,
            "duration_sec": round(duration, 3),
            "tool_calls": tool_calls,
        }


def test_generate(model_name: str, prompt: str = "Explain the Norwegian salmon traffic light system in 2 short bullet points."):
    clean_name = model_name if model_name.startswith("models/") else f"models/{model_name}"
    url = f"{BASE_URL}/{clean_name}:generateContent?key={API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        duration = time.perf_counter() - t0
        res = json.loads(resp.read().decode("utf-8"))
        candidates = res.get("candidates", [])
        text = ""
        finish_reason = ""
        if candidates:
            candidate = candidates[0]
            finish_reason = candidate.get("finishReason", "")
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        usage = res.get("usageMetadata", {})
        return {
            "model": clean_name,
            "status": resp.status,
            "duration_sec": round(duration, 3),
            "response": text.strip(),
            "finish_reason": finish_reason,
            "usage": usage,
        }

    clean_name = model_name if model_name.startswith("models/") else f"models/{model_name}"
    url = f"{BASE_URL}/{clean_name}:generateContent?key={API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        duration = time.perf_counter() - t0
        res = json.loads(resp.read().decode("utf-8"))
        candidates = res.get("candidates", [])
        text = ""
        finish_reason = ""
        if candidates:
            candidate = candidates[0]
            finish_reason = candidate.get("finishReason", "")
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        usage = res.get("usageMetadata", {})
        return {
            "model": clean_name,
            "status": resp.status,
            "duration_sec": round(duration, 3),
            "response": text.strip(),
            "finish_reason": finish_reason,
            "usage": usage,
            "full_json": res,
        }


def main():
    print("=" * 60)
    print("TESTING GEMINI API GENERATION...")
    print("=" * 60)

    test_models = [
        "gemini-3.8-flash",
    ]

    for model in test_models:
        print(f"\n---> Testing model: {model} ...")
        try:
            result = test_generate(model)
            print(f"Status: {result['status']} | Latency: {result['duration_sec']}s")
            print(f"Prompt tokens: {result['usage'].get('promptTokenCount')} | Candidate tokens: {result['usage'].get('candidatesTokenCount')}")
            print("Response:")
            for line in result["response"].split("\n"):
                print("  " + line)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            print(f"HTTPError {e.code}: {err_body[:300]}")
        except Exception as e:
            print(f"Error: {e}")


    print("\n" + "=" * 60)
    print("TESTING TOOL CALLING (FUNCTION CALLING)...")
    print("=" * 60)
    try:
        tool_res = test_tool_calling("gemini-3.8-flash")
        print(f"Status: {tool_res['status']} | Latency: {tool_res['duration_sec']}s")
        print(f"Tool calls returned: {json.dumps(tool_res['tool_calls'], indent=2)}")
    except Exception as e:
        print("Tool calling error:", e)


if __name__ == "__main__":
    main()
