import logging

from environs import Env

env = Env()
logger = logging.getLogger(__name__)

environment = env("ENVIRONMENT", "local")

if environment == "local":
    from .local import Config
elif environment == "staging":
    from .staging import Config
elif environment == "production":
    from .production import Config
else:
    raise ValueError("Invalid environment specified.")

logger.info(f"Run environment: {environment}")

config = Config()
