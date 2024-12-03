from dependency_injector import containers, providers
from .test_service import TestService


class TestContainer(containers.DeclarativeContainer):
    service: providers.Singleton[TestService] = providers.Singleton(TestService)
