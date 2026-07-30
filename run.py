import sys
import logging
from config import validate_config
from bot.db import init_db
from bot.render_health_server import start_render_health_server
from bot.telegram_handler import TelegramHandler

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    validate_config()
    init_db()
    start_render_health_server()

    handler = TelegramHandler()
    handler.start_polling_loop()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSession interrupted cleanly.")
        sys.exit(0)
