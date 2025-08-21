from environs import Env

env = Env()


class BaseConfig:
    LOG_LEVEL = env("LOG_LEVEL", "INFO")
    ENVIRONMENT = env("ENVIRONMENT", "local")

    #
    # Timezone
    #

    DEFAULT_TIMEZONE = env("DEFAULT_TIMEZONE", "America/Guayaquil")
