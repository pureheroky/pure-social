import logging
from pathlib import Path


def setup_log(service_name: str) -> logging.Logger:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logs_dir = Path(__file__).resolve().parents[2] / "logs" / service_name
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "log.log"

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="{asctime} - {levelname} - {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    if not logger.hasHandlers():
        logger.addHandler(file_handler)

    return logger
