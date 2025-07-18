import logging
from pathlib import Path


def setup_log(service_name: str, module_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    logs_dir = Path(__file__).resolve().parents[2] / "logs" / service_name
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "log.log"

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        formatter = logging.Formatter(
            fmt="{asctime} - {levelname} - {message}",
            style="{",
            datefmt="%Y-%m-%d %H:%M",
        )

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.debug(f"Logger initialized for {service_name} at {log_file}")
    return logger
