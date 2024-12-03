from typing import Sequence

from aiogram import Router

from .onboarding import router as onboarding_router
from .ai_talking import router as ai_router
from .admin import router as admin_router
from .test import router as test

from ..config import BotConfig


def get_routers(config: BotConfig) -> Sequence[Router]:
    routers: list[Router] = [onboarding_router, test, ai_router, admin_router]
    return routers
