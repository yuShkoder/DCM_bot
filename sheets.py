import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_ID = os.environ["SHEET_ID"]  # ID таблицы из URL Google Sheets

# Заголовки вкладок
HEADERS_OFFERS = ["Название", "Тип", "Купон", "Комиссия", "От кого", "Дата размещения", "Комментарий"]
HEADERS_DEALS  = ["Название", "Объём", "Тип", "Дата покупки", "Репо", "Комментарий", "Дата добавления"]
HEADERS_ARCHIVE = HEADERS_DEALS


class SheetsClient:
    def __init__(self):
        creds_json = os.environ["GOOGLE_CREDS_JSON"]
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open_by_key(SHEET_ID)
        self._ensure_headers()

    def _ensure_headers(self):
        """Создаёт заголовки если вкладки пустые"""
        for tab, headers in [
            ("Предложения", HEADERS_OFFERS),
            ("Размещения",  HEADERS_DEALS),
            ("Архив",       HEADERS_ARCHIVE),
        ]:
            ws = self.sh.worksheet(tab)
            if not ws.row_values(1):
                ws.append_row(headers, value_input_option="USER_ENTERED")

    def append_offer(self, row: list):
        ws = self.sh.worksheet("Предложения")
        ws.append_row(row, value_input_option="USER_ENTERED")

    def append_deal(self, row: list):
        """row = [name, volume, type, date, repo, comment] — добавляем дату автоматически"""
        today = datetime.now().strftime("%d.%m.%Y")
        full_row = row + [today]
        ws = self.sh.worksheet("Размещения")
        ws.append_row(full_row, value_input_option="USER_ENTERED")

    def archive_old_deals(self):
        """Переносит в Архив строки из Размещений старше 14 дней"""
        ws_deals   = self.sh.worksheet("Размещения")
        ws_archive = self.sh.worksheet("Архив")

        all_rows = ws_deals.get_all_values()
        if len(all_rows) <= 1:
            return  # только заголовок

        headers = all_rows[0]
        date_col_idx = headers.index("Дата добавления")  # последняя колонка

        cutoff = datetime.now() - timedelta(days=14)
        rows_to_keep   = [headers]
        rows_to_archive = []

        for row in all_rows[1:]:
            if not row or all(cell == "" for cell in row):
                continue
            try:
                row_date = datetime.strptime(row[date_col_idx], "%d.%m.%Y")
                if row_date < cutoff:
                    rows_to_archive.append(row)
                else:
                    rows_to_keep.append(row)
            except (ValueError, IndexError):
                rows_to_keep.append(row)  # не удалось распознать дату — оставляем

        if rows_to_archive:
            ws_archive.append_rows(rows_to_archive, value_input_option="USER_ENTERED")

            # Очищаем Размещения и пишем только оставшиеся строки
            ws_deals.clear()
            ws_deals.update("A1", rows_to_keep, value_input_option="USER_ENTERED")

        return len(rows_to_archive)
