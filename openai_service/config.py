from utils.env import EnvConfValue

import os
from typing import Optional


class OpenaiConfig():
    def __init__(self, environment: Optional[dict] = None):
        # Используем переменные окружения
        self.environment = environment or os.environ

        self.proxy: EnvConfValue[str] = EnvConfValue("OPENAI_PROXY")
        self.token: EnvConfValue[str] = EnvConfValue("OPENAI_TOKEN")
        self.model_id: EnvConfValue[str] = EnvConfValue("OPENAI_MODEL_ID")
        self.interval_s: EnvConfValue[float] = EnvConfValue("OPENAI_ANIMATION_INTERVAL")

        self.tokens_limit: EnvConfValue[int] = EnvConfValue("OPENAI_TOKENS_LIMIT")
        self.messages_limit: EnvConfValue[int] = EnvConfValue("OPENAI_MESSAGES_LIMIT")

        self.tokens_user_limit:  EnvConfValue[int] = EnvConfValue("OPENAI_TOKENS_USER_LIMIT")
        self.messages_user_limit:  EnvConfValue[int] = EnvConfValue("OPENAI_MESSAGES_USER_LIMIT")


class PromptConfig():
    def __init__(self, environment: Optional[dict] = None):
        # Используем переменные окружения
        self.environment = environment or os.environ

