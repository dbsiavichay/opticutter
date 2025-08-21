from .base import BaseConfig, env


class Config(BaseConfig):
    LOG_LEVEL = env("LOG_LEVEL", "DEBUG")
