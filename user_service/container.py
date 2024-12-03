import logging
from dependency_injector import containers, providers

from .user_service import UserService

class UserServiceContainer(containers.DeclarativeContainer):
    user_service: providers.Singleton[UserService] = providers.Singleton(UserService)

