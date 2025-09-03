# app/services/scoring.py
import base64
from math import floor

def _b64dec(s):
    if s is None:
        return None
    try:
        return base64.b64decode(s).decode("utf-8", errors="replace")
    except Exception:
        return None

def score_batch(task, batch_result: dict) -> tuple[int, str, dict]:
    """
    Возвращает (points, verdict, summary_json).
    Ожидаем формат batch_result["results"] = [{ "stdout": <b64>, "status": {...}, ...}, ...]
    Если формата нет — ставим 'PENDING'.
    """
    results = (batch_result or {}).get("results")
    if not isinstance(results, list):
        return 0, "PENDING", batch_result or {}

    n = len(results) if results else 0
    if n == 0:
        return 0, "PENDING", batch_result

    # Равномерно распределим баллы
    per = max(1, floor(task.max_points / n))
    gained = 0
    all_ok = True

    # Если мы отправляли expected_output, ExecEngine обычно сравнивает сам,
    # но на случай отсутствия явного флага — сравним stdout/expected_output сами по доступным полям.
    for r in results:
        status = (r.get("status") or {}).get("description") or r.get("verdict") or ""
        status = str(status).upper()
        if "ACCEPT" in status or status in ("OK", "SUCCESS"):
            gained += per
            continue

        # fallback: сравнить stdout vs expected_output, если присутствуют
        out = _b64dec(r.get("stdout"))
        exp = _b64dec(r.get("expected_output"))  # некоторые API возвращают echo ожидаемого
        if exp is not None and out is not None and out.strip() == exp.strip():
            gained += per
        else:
            all_ok = False

    verdict = "OK" if all_ok and gained >= task.max_points else ("PARTIAL" if gained > 0 else "WA")
    # округлим вверх до max_points если все тесты прошли
    if verdict == "OK":
        gained = task.max_points
    return int(gained), verdict, batch_result
