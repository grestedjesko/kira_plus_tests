from typing import Optional
import os

class EnvConfValue:
    def __init__(self, name, default=None, converter=None):
        self.name = name
        self.default = default
        self.converter = converter

    @property
    def value(self):
        return self.get()

    def get(self, environment: Optional[dict] = None):
        if environment:
            value = environment.get(self.name, self.default)
        else:
            value = os.getenv(self.name, self.default)

        if value is None:
            raise RuntimeError(f"Environment variable {self.name} is not set and has no default value.")

        if self.converter:
            return self.converter(value)
        return value
