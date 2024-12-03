from utils.env import EnvConfValue

import os
from typing import Optional


class TableConfig():
    def __init__(self, environment: Optional[dict] = None):
        # Используем переменные окружения
        self.environment = environment or os.environ

        self.credentials: EnvConfValue[str] = EnvConfValue("GOOGLE_CREDENTIALS")
        self.sheet_id: EnvConfValue[str] = EnvConfValue("GOOGLE_SHEET_ID")
