import sys
from bot.db import init_db
from bot.telegram_handler import TelegramHandler

def main():
    # Enforce schema validation
    init_db()
    
    # Initialize long polling sequence with custom 2-hour timeout
    handler = TelegramHandler()
    handler.start_polling_loop(timeout_hours=2.0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSession interrupted cleanly.")
        sys.exit(0)