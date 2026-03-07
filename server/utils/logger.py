"""
server/utils/logger.py
Configuración de logging profesional para el CNS Server.
Registra en consola (coloreado) y en archivo rotativo.
"""

import logging
import logging.handlers
import os
from pathlib import Path

# ─── Constantes ───────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / "server_activity.log"
LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 5 * 1024 * 1024   # 5 MB por archivo
BACKUP_COUNT = 5               # mantener 5 archivos históricos


# ─── Colores ANSI para consola ─────────────────────────────────────────────────
class _ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG:    "\033[36m",   # Cyan
        logging.INFO:     "\033[32m",   # Verde
        logging.WARNING:  "\033[33m",   # Amarillo
        logging.ERROR:    "\033[31m",   # Rojo
        logging.CRITICAL: "\033[1;31m", # Rojo negrita
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(name: str = "CNS") -> logging.Logger:
    """
    Retorna un logger configurado con:
      - StreamHandler (consola, coloreado)
      - RotatingFileHandler (logs/server_activity.log)
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        # Evitar handlers duplicados si se llama varias veces
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Consola ──────────────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        _ColorFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    )

    # ── Archivo rotativo ──────────────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("Sistema de logging inicializado. Archivo: %s", LOG_FILE)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Obtiene un sub-logger del logger raíz CNS."""
    return logging.getLogger(f"CNS.{name}")
