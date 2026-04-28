"""
Запускай этот файл отдельным процессом на Railway,
или добавь вызов schedule_jobs() в конец main() в bot.py
через asyncio в отдельном потоке.
"""
import schedule
import time
import logging
from sheets import SheetsClient

logger = logging.getLogger(__name__)


def run_archive():
    try:
        sheets = SheetsClient()
        count = sheets.archive_old_deals()
        if count:
            logger.info(f"Архив: перенесено {count} строк")
        else:
            logger.info("Архив: нечего переносить")
    except Exception as e:
        logger.error(f"Ошибка архивирования: {e}")


# Каждую ночь в 02:00
schedule.every().day.at("02:00").do(run_archive)


def run_scheduler():
    logger.info("Планировщик запущен")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_scheduler()
