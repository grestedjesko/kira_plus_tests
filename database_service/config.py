from utils.env import EnvConfValue

import os
from typing import Literal, cast, Optional, Dict, Any

class PostgresConfig():
    def __init__(self, environment: Optional[dict] = None):
        # Используем переменные окружения
        self.environment = environment or os.environ
        self.host: EnvConfValue[str] = EnvConfValue("POSTGRES_HOST")
        self.port: EnvConfValue[int] = EnvConfValue("POSTGRES_PORT", default="5432", converter=int)
        self.username: EnvConfValue[str] = EnvConfValue("POSTGRES_USER")
        self.password: EnvConfValue[str] = EnvConfValue("POSTGRES_PASSWORD")
        self.db: EnvConfValue[str] = EnvConfValue("POSTGRES_DB")
