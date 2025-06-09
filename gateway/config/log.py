import logging

from litestar.logging.config import LoggingConfig
from msgspec.json import Encoder

log_config = LoggingConfig(
    loggers={
        "root": {"level": logging.getLevelName(logging.INFO), "handlers": ["console"]},
        "httpx": {"level": logging.getLevelName(logging.WARNING), "handlers": ["console"]},
        "aiobotocore": {"level": logging.getLevelName(logging.WARNING), "handlers": ["console"]},
        "narwhal_gateway": {
            "level": "INFO",
            "handlers": ["queue_listener"],
        },
    },
    formatters={"standard": {"format": "%(levelname)s: %(asctime)s - %(name)s - %(message)s"}},
)

logger = log_config.configure()()
JE = Encoder()
