import base64
import time
from typing import Iterable, Optional

import requests
from flask import current_app




class ExecEngineClientV2:
    """
    Мини-клиент под ExecEngine v2:
      - POST /auth/login/ -> {"access_token": "..."}
      - POST /submissions/batch/ -> {"batch_token": "..."}
      - GET  /submissions/batch/{batch_token}/ -> {"status": "...", "results": [...] }   # <-- ожидаем такой контракт
    """

    def __init__(self, base_url: str, api_prefix: str = "/v2", timeout: int = 15,
                 username: Optional[str] = None, password: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api = api_prefix if api_prefix.startswith("/") else f"/{api_prefix}"
        self.timeout = timeout
        self.username = username
        self.password = password
        self._token = None
        self._token_ts = 0
        self._token_ttl = 60 * 25  # минут 25 (в ini по умолчанию 30)

    # ---------- utils ----------

    @staticmethod
    def _b64(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        if isinstance(s, str):
            return base64.b64encode(s.encode("utf-8")).decode("ascii")
        raise TypeError("Expected str for base64")

    def _headers(self) -> dict:
        tok = self._get_token()
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    # ---------- auth ----------

    def _get_token(self) -> Optional[str]:
        # простой кеш токена, без рефрешей
        now = time.time()
        if self._token and (now - self._token_ts) < self._token_ttl:
            return self._token

        if not self.username or not self.password:
            return None

        resp = requests.post(
            f"{self.base_url}{self.api}/auth/login/",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("access_token")
        self._token_ts = now
        return self._token

    # ---------- submissions ----------

    def submit_batch(
            self,
            *,
            language_id: int,
            source_code: str,
            tests: Optional[Iterable[dict]] = None,
            time_limit: Optional[float] = None,
            extra_time: Optional[float] = None,
            wall_time_limit: Optional[float] = None,
            memory_limit: Optional[int] = None,
            redirect_stderr_to_stdout: Optional[bool] = None,
            enable_network: Optional[bool] = None,
            max_file_size: Optional[int] = None,
    ) -> dict:
        """
        tests: iterable of {"stdin": str|None, "expected_output": str|None}
        Возвращает {"batch_token": "..."} как в твоём примере.
        """
        # дефолты из конфига
        cfg = current_app.config
        tl = cfg.get("EE_TIME_LIMIT") if time_limit is None else time_limit
        et = cfg.get("EE_EXTRA_TIME") if extra_time is None else extra_time
        wl = cfg.get("EE_WALL_TIME_LIMIT") if wall_time_limit is None else wall_time_limit
        ml = cfg.get("EE_MEMORY_LIMIT") if memory_limit is None else memory_limit
        rse = cfg.get("EE_REDIRECT_STDERR") if redirect_stderr_to_stdout is None else redirect_stderr_to_stdout
        net = cfg.get("EE_ENABLE_NETWORK") if enable_network is None else enable_network
        mfs = cfg.get("EE_MAX_FILE_SIZE") if max_file_size is None else max_file_size

        submissions = []
        if not tests:
            # хотя бы один сабмишен без stdin/expected_output — на случай задач без тестов
            tests = [{"stdin": None, "expected_output": None}]

        sc_b64 = self._b64(source_code)
        for t in tests:
            sub = {
                "language_id": int(71),
                "source_code": sc_b64,
                "stdin": self._b64(t.get("stdin")),
                "expected_output": self._b64(t.get("expected_output")),
                "compiler_options": None,
                "command_line_args": None,
                "time_limit": float(tl),
                "extra_time": float(et),
                "wall_time_limit": float(wl),
                "memory_limit": int(ml),
                "redirect_stderr_to_stdout": bool(rse),
                "enable_network": bool(net),
                "max_file_size": int(mfs),
            }
            submissions.append(sub)

        payload = {"submissions": submissions}
        r = requests.post(
            f"{self.base_url}{self.api}/submissions/batch/",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()  # ожидаем {"batch_token": "..."}

    def wait_batch_results(self, batch_token: str, max_wait_s: float = 8.0, step_s: float = 0.5) -> dict:
        """
        Небольшой опрос результата батча.
        Ожидаем контракт вида {"status": "FINISHED", "results": [...] }
        Если контракт иной — вернём что получилось (raw JSON), не упадём.
        """
        url = f"{self.base_url}{self.api}/submissions/batch/{batch_token}/"
        deadline = time.time() + max_wait_s
        last = None
        while time.time() < deadline:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)

            # на случай иного роутинга — один бэкап-вариант (можно убрать, если не нужен)
            if resp.status_code == 404:
                resp = requests.get(f"{self.base_url}{self.api}/submissions/batch/?batch_token={batch_token}",
                                    headers=self._headers(), timeout=self.timeout)

            if resp.ok:
                try:
                    data = resp.json()
                    last = data
                except requests.exceptions.JSONDecodeError:
                    # Если ответ не JSON, просто пропускаем и ждём следующего
                    time.sleep(step_s)
                    continue

                # Проверяем, является ли ответ списком (что, вероятно, является причиной ошибки)
                if isinstance(data, list):
                    # Если это список, и в нём есть хотя бы один элемент с результатами,
                    # можно считать, что он готов. Можно скорректировать логику.
                    if any("results" in item for item in data):
                        return {"status": "FINISHED", "results": data}

                    # Если нужно, можно добавить более сложную логику проверки статуса
                    # Например, `if all("status" in item and item["status"] == "FINISHED" for item in data):`

                # Иначе, продолжаем с оригинальной логикой для словаря
                elif isinstance(data, dict):
                    status = (str(data.get("status", ""))).lower()
                    if "finish" in status or "done" in status or "completed" in status:
                        return data

                    # иногда ответ уже содержит "results" — тоже считаем финалом
                    if "results" in data:
                        return data

            time.sleep(step_s)

        return last or {"status": "PENDING", "batch_token": batch_token}


def get_client() -> ExecEngineClientV2:
    cfg = current_app.config
    return ExecEngineClientV2(
        base_url=cfg["EXECENGINE_BASE_URL"],
        api_prefix=cfg.get("EXECENGINE_API_PREFIX", "/v2"),
        timeout=cfg.get("EXECENGINE_TIMEOUT", 15),
        username=cfg.get("EXECENGINE_USERNAME"),
        password=cfg.get("EXECENGINE_PASSWORD"),
    )
