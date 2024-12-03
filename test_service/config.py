import os
from typing import Optional


class TestConfig():
    def __init__(self, environment: Optional[dict] = None):
        # Используем переменные окружения
        self.environment = environment or os.environ