import logging

from config import Settings


def setup_logging(settings: Settings) -> None:
    logging.basicConfig(
        level="INFO", format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
