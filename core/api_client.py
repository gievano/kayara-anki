import json
import time
import traceback

import requests


class ApiResult:
    def __init__(self, success, content="", error=None, retryable=False):
        self.success = success
        self.content = content
        self.error = error
        self.retryable = retryable


class KayaraClient:
    def __init__(self, config, addon_name):
        self.config = config
        self.addon_name = addon_name
        self._session = requests.Session()

    def _log(self, msg):
        if self.config.get("features", {}).get("debug_log"):
            print(f"[kayara] {msg}")

    def send_message(self, messages, model_id, temperature):
        url = self.config["api_endpoint"].rstrip("/") + "/chat/completions"
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.config.get("max_tokens", 1000),
        }
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json",
        }
        retries = 2
        delay = 1

        last_err = None
        for attempt in range(retries + 1):
            try:
                self._log(f"POST {url} model={model_id} attempt={attempt + 1}")
                resp = self._session.post(
                    url, json=payload, headers=headers, timeout=30
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    self._log(f"OK, {len(content)} chars")
                    return ApiResult(True, content=content)
                if resp.status_code in (401, 403):
                    return ApiResult(False, error="🔑 API key tidak valid. Cek config.")
                if resp.status_code == 429:
                    last_err = "⏳ Rate limit. Tunggu sebentar lalu retry."
                    return ApiResult(False, error=last_err)
                last_err = f"❌ API error {resp.status_code}: {resp.text[:200]}"
            except requests.exceptions.Timeout:
                last_err = "⏱️ Request timeout. API tidak merespons."
            except requests.exceptions.ConnectionError:
                return ApiResult(
                    False,
                    error="❌ Tidak bisa connect ke API. Pastikan OmniRoute jalan & cek endpoint di config.",
                )
            except (KeyError, IndexError, json.JSONDecodeError):
                last_err = "❌ Format response tidak dikenal."
            except Exception as e:
                self._log(traceback.format_exc())
                last_err = f"❌ Error: {e}"

            if attempt < retries:
                time.sleep(delay)

        return ApiResult(False, error=last_err, retryable=True)

    def test_connection(self, model_id):
        r = self.send_message(
            [{"role": "user", "content": "ping"}], model_id, 0.0
        )
        return r.success

    def send_message_stream(self, messages, model_id, temperature, on_chunk):
        """SSE streaming (OpenAI-compatible). on_chunk(str) dipanggil per delta.
        Return ApiResult berisi konten lengkap. Fallback error sama seperti send_message."""
        url = self.config["api_endpoint"].rstrip("/") + "/chat/completions"
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.config.get("max_tokens", 1000),
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json",
        }
        try:
            resp = self._session.post(
                url, json=payload, headers=headers, timeout=30, stream=True
            )
            if resp.status_code != 200:
                return ApiResult(
                    False, error=f"❌ API error {resp.status_code}: {resp.text[:200]}"
                )
            # ponytail: SSE header jarang bawa charset → requests default ISO-8859-1
            # dan teks Jepang jadi mojibake (æ¿å¤). Paksa UTF-8.
            resp.encoding = "utf-8"
            full = []
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if delta:
                    full.append(delta)
                    on_chunk(delta)
            content = "".join(full)
            if not content:
                return ApiResult(False, error="❌ Stream kosong dari API.", retryable=True)
            return ApiResult(True, content=content)
        except requests.exceptions.ConnectionError:
            return ApiResult(
                False,
                error="❌ Tidak bisa connect ke API. Pastikan OmniRoute jalan & cek endpoint di config.",
                retryable=True,
            )
        except Exception as e:
            self._log(traceback.format_exc())
            return ApiResult(False, error=f"❌ Error: {e}", retryable=True)
