from dataclasses import dataclass
import os
from typing import Literal, cast, Optional, Dict, Any
from utils.env import EnvConfValue

@dataclass
class TelegramConfig:
    token = EnvConfValue("TELEGRAM_TOKEN")
    logs_chat_id = EnvConfValue("TELEGRAM_LOGS_CHAT_ID")
    admin = EnvConfValue("TELEGRAM_ADMIN")


class BotConfig:
    def __init__(self, environment: Optional[dict] = None):
        # Используем переменные окружения
        self.environment = environment or os.environ
        self.telegram = TelegramConfig()