import re
CYR6 = re.compile(r"^[А-ЯЁ]{6}$")  # только заглавные кириллические

def normalize_code(raw: str) -> str:
    raw = (raw or "").strip().upper().replace("Ё", "Ё")  # явная фиксация
    return raw

def is_valid_code(code: str) -> bool:
    return bool(CYR6.match(code))
