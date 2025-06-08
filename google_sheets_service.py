"""
Сервис для экспорта данных в Google Sheets
"""
import logging
from typing import List, Dict, Any
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

from config import config
from models import DailyMetrics

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Сервис для работы с Google Sheets"""
    
    def __init__(self):
        self._client = None
        self._worksheet = None
    
    async def _get_client(self):
        """Получение клиента Google Sheets"""
        if self._client is None:
            try:
                scope = [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/spreadsheets'
                ]
                
                creds = Credentials.from_service_account_file(
                    config.google_credentials_file, 
                    scopes=scope
                )
                
                self._client = gspread.authorize(creds)
                logger.info("✅ Google Sheets клиент инициализирован")
                
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации Google Sheets: {e}")
                raise
        
        return self._client
    
    async def _get_worksheet(self):
        """Получение рабочего листа"""
        if self._worksheet is None:
            try:
                client = await self._get_client()
                spreadsheet = client.open_by_key(config.google_sheet_id)
                
                # Попытка получить существующий лист
                try:
                    self._worksheet = spreadsheet.worksheet(config.google_sheet_name)
                except gspread.WorksheetNotFound:
                    # Создание нового листа если не существует
                    self._worksheet = spreadsheet.add_worksheet(
                        title=config.google_sheet_name, 
                        rows=1000, 
                        cols=25
                    )
                    await self._setup_header()
                    logger.info(f"✅ Создан новый лист: {config.google_sheet_name}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка получения листа: {e}")
                raise
        
        return self._worksheet
    
    async def _setup_header(self):
        """Настройка заголовков таблицы"""
        headers = [
            "Дата",
            "Менеджер",
            "К-во диалогов всего за день",
            "К-во новых клиентов",
            "К-во активных клиентов",
            "К-во новичков написало",
            "К-во новичков купило",
            "К-во разослано сообщений о продлении",
            "К-во клиентов продлило",
            "К-во отказов",
            "К-во смс старичкам без ответа",
            "К-во выдано бонусов",
            "К-во получено отзывов за день от клиентов",
            "Фактическая выручка за день",
            "Фактическая выручка по новичкам",
            "Мпстатс",
            "Вайлдбокс",
            "Маркетгуру",
            "Маниплейс",
            "Мпстатс+маркетуру",
            "Мпстатс+вайлдбокс",
            "Мпстатс+маниплейс"
        ]
        
        try:
            worksheet = await self._get_worksheet()
            worksheet.insert_row(headers, 1)
            
            # Форматирование заголовков
            worksheet.format('A1:V1', {
                'backgroundColor': {'red': 0.8, 'green': 0.8, 'blue': 0.8},
                'textFormat': {'bold': True, 'fontSize': 11},
                'horizontalAlignment': 'CENTER'
            })
            
            logger.info("✅ Заголовки таблицы настроены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки заголовков: {e}")
            raise
    
    async def export_daily_metrics(self, metrics_list: List[DailyMetrics]) -> bool:
        """
        Экспорт дневных метрик в Google Sheets
        
        Args:
            metrics_list: Список метрик для экспорта
            
        Returns:
            True если успешно
        """
        if not metrics_list:
            logger.info("Нет метрик для экспорта")
            return True
        
        try:
            worksheet = await self._get_worksheet()
            
            # Подготовка данных для вставки
            rows_to_insert = []
            for metrics in metrics_list:
                row_data = [
                    metrics.date.strftime("%Y-%m-%d"),
                    metrics.manager.full_name,
                    metrics.total_dialogs,
                    metrics.new_clients,
                    metrics.active_clients,
                    metrics.newcomers_contacted,
                    metrics.newcomers_purchased,
                    metrics.renewal_messages_sent,
                    metrics.clients_renewed,
                    metrics.rejections,
                    metrics.sms_silent_clients,
                    metrics.bonuses_given,
                    metrics.reviews_received,
                    metrics.total_revenue,
                    metrics.newcomer_revenue,
                    metrics.mpstats_sold,
                    metrics.wildberries_sold,
                    metrics.marketguru_sold,
                    metrics.maniplace_sold,
                    metrics.mpstats_marketguru_sold,
                    metrics.mpstats_wildberries_sold,
                    metrics.mpstats_maniplace_sold
                ]
                rows_to_insert.append(row_data)
            
            # Вставка данных
            worksheet.append_rows(rows_to_insert, value_input_option='USER_ENTERED')
            
            logger.info(f"✅ Экспортировано {len(rows_to_insert)} строк в Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта в Google Sheets: {e}")
            return False
    
    async def export_single_metrics(self, metrics: DailyMetrics) -> bool:
        """
        Экспорт одной записи метрик
        
        Args:
            metrics: Метрики для экспорта
            
        Returns:
            True если успешно
        """
        return await self.export_daily_metrics([metrics])
    
    async def check_connection(self) -> bool:
        """
        Проверка соединения с Google Sheets
        
        Returns:
            True если соединение работает
        """
        try:
            worksheet = await self._get_worksheet()
            # Попробуем получить первую ячейку
            worksheet.acell('A1')
            logger.info("✅ Соединение с Google Sheets работает")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка соединения с Google Sheets: {e}")
            return False
    
    async def get_last_export_date(self) -> str:
        """
        Получение даты последнего экспорта
        
        Returns:
            Дата в формате YYYY-MM-DD или None
        """
        try:
            worksheet = await self._get_worksheet()
            
            # Получаем все значения в колонке A (даты)
            dates = worksheet.col_values(1)
            
            # Удаляем заголовок и пустые ячейки
            dates = [date for date in dates[1:] if date]
            
            if dates:
                # Возвращаем последнюю дату
                return dates[-1]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения последней даты: {e}")
            return None
    
    async def clear_sheet(self) -> bool:
        """
        Очистка листа (для отладки)
        
        Returns:
            True если успешно
        """
        try:
            worksheet = await self._get_worksheet()
            worksheet.clear()
            await self._setup_header()
            logger.info("✅ Лист очищен и заголовки восстановлены")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки листа: {e}")
            return False
    
    async def update_cell_formatting(self):
        """Обновление форматирования ячеек"""
        try:
            worksheet = await self._get_worksheet()
            
            # Автоширина колонок
            worksheet.columns_auto_resize(0, 22)
            
            # Выравнивание по центру для числовых колонок
            worksheet.format('C:V', {
                'horizontalAlignment': 'CENTER',
                'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}
            })
            
            # Форматирование денежных колонок
            worksheet.format('N:O', {
                'numberFormat': {'type': 'CURRENCY', 'pattern': '#,##0₽'}
            })
            
            logger.info("✅ Форматирование обновлено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования: {e}")


# Глобальный экземпляр сервиса
google_sheets_service = GoogleSheetsService()
