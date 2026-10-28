# settings.py — Global config, all spiders read from here

HEADLESS        = True
TIMEOUT         = 30_000
RETRIES         = 3
RETRY_DELAY     = 1.0
VIEWPORT        = {"width": 1280, "height": 800}
BLOCK_IMAGES    = True
BLOCK_FONTS     = False
USER_AGENT      = None
PROXY           = None

CONCURRENCY     = 3
WAIT_UNTIL      = "domcontentloaded"

OUTPUT_DIR      = "output"
LOG_FILE        = "logs/scraper.log"