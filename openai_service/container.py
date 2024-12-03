from dependency_injector import containers, providers

from .interaction_manager import InteractionManager
from .prompt_manager import PromptManager
from .limit_manager import LimitManager
from .openai_service import OpenaiService

from .config import OpenaiConfig


class OpenaiServiceContainer(containers.DeclarativeContainer):
    config: providers.Singleton[OpenaiConfig] = providers.Singleton(OpenaiConfig)

    interaction_manager: providers.Singleton[InteractionManager] = providers.Singleton(InteractionManager, config=config)
    prompt_manager: providers.Singleton[PromptManager] = providers.Singleton(PromptManager, config=config)
    limit_manager: providers.Singleton[LimitManager] = providers.Singleton(LimitManager, config=config)

    service: providers.Singleton[OpenaiConfig] = providers.Singleton(
        OpenaiService,
        interaction_manager=interaction_manager,
        prompt_manager=prompt_manager,
        limit_manager=limit_manager,
    )