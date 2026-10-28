import logging


def get_logger(name: str) -> logging.Logger:
    """
    Logger compatible with uvicorn + FastAPI lifecycle.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Attach uvicorn error handlers (startup / shutdown logs)
    uvicorn_logger = logging.getLogger("uvicorn.error")

    if uvicorn_logger.handlers:
        logger.handlers = uvicorn_logger.handlers
        logger.propagate = False

    return logger
