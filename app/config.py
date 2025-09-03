import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/execschool")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ExecEngine
    EXECENGINE_BASE_URL = os.getenv("EXECENGINE_BASE_URL", "http://execengine:8000")
    EXECENGINE_TIMEOUT = int(os.getenv("EXECENGINE_TIMEOUT", "25"))  # сек.
    EXECENGINE_BASE_URL = os.getenv("EXECENGINE_BASE_URL", "http://execengine:8000")
    EXECENGINE_API_PREFIX = os.getenv("EXECENGINE_API_PREFIX", "/v2")
    EXECENGINE_TIMEOUT = int(os.getenv("EXECENGINE_TIMEOUT", "15"))

    # Сервисный пользователь для ExecEngine
    EXECENGINE_USERNAME = os.getenv("EXECENGINE_USERNAME", "admin")
    EXECENGINE_PASSWORD = os.getenv("EXECENGINE_PASSWORD", "admin")

    # Дефолтные лимиты (могут переопределяться на задаче)
    EE_TIME_LIMIT = float(os.getenv("EE_TIME_LIMIT", "2"))
    EE_EXTRA_TIME = float(os.getenv("EE_EXTRA_TIME", "0.5"))
    EE_WALL_TIME_LIMIT = float(os.getenv("EE_WALL_TIME_LIMIT", "3"))
    EE_MEMORY_LIMIT = int(os.getenv("EE_MEMORY_LIMIT", "128000"))
    EE_REDIRECT_STDERR = os.getenv("EE_REDIRECT_STDERR", "true").lower() == "true"
    EE_ENABLE_NETWORK = os.getenv("EE_ENABLE_NETWORK", "false").lower() == "false"  # по умолчанию запрещаем сеть
    EE_MAX_FILE_SIZE = int(os.getenv("EE_MAX_FILE_SIZE", "1024"))
    TEMPLATES_AUTO_RELOAD = True
