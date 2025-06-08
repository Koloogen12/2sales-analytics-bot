"""
Модели базы данных для системы учета метрик продаж
"""
from tortoise import Model, fields
from datetime import datetime, date
from typing import Dict, Any, Optional
import json


class Manager(Model):
    """Менеджер по продажам"""
    id = fields.IntField(pk=True)
    telegram_user_id = fields.BigIntField(unique=True, description="ID пользователя Telegram")
    full_name = fields.CharField(max_length=100, description="ФИО менеджера")
    username = fields.CharField(max_length=100, null=True, description="Telegram username")
    is_active = fields.BooleanField(default=True, description="Активен ли менеджер")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "managers"

    def __str__(self):
        return f"Manager: {self.full_name} (@{self.username})"


class DailyMetrics(Model):
    """Ежедневные метрики менеджера"""
    id = fields.IntField(pk=True)
    manager = fields.ForeignKeyField("models.Manager", related_name="daily_metrics")
    date = fields.DateField(description="Дата метрик")
    
    # Основные метрики
    total_dialogs = fields.IntField(default=0, description="Количество диалогов всего за день")
    new_clients = fields.IntField(default=0, description="Количество новых клиентов")
    active_clients = fields.IntField(default=0, description="Количество активных клиентов")
    newcomers_contacted = fields.IntField(default=0, description="Количество новичков написало")
    newcomers_purchased = fields.IntField(default=0, description="Количество новичков купило")
    renewal_messages_sent = fields.IntField(default=0, description="Количество разослано сообщений о продлении")
    clients_renewed = fields.IntField(default=0, description="Количество клиентов продлило")
    rejections = fields.IntField(default=0, description="Количество отказов")
    sms_silent_clients = fields.IntField(default=0, description="Количество смс старичкам без ответа")
    bonuses_given = fields.IntField(default=0, description="Количество выдано бонусов")
    reviews_received = fields.IntField(default=0, description="Количество получено отзывов за день от клиентов")
    
    # Финансовые метрики
    total_revenue = fields.FloatField(default=0.0, description="Фактическая выручка за день")
    newcomer_revenue = fields.FloatField(default=0.0, description="Фактическая выручка по новичкам")
    
    # Продукты (единичные)
    mpstats_sold = fields.IntField(default=0, description="Продано МПСтатс")
    wildberries_sold = fields.IntField(default=0, description="Продано Вайлдберрис")
    marketguru_sold = fields.IntField(default=0, description="Продано Маркетгуру")
    maniplace_sold = fields.IntField(default=0, description="Продано Маниплейс")
    
    # Связки продуктов
    mpstats_marketguru_sold = fields.IntField(default=0, description="Продано МПСтатс+Маркетгуру")
    mpstats_wildberries_sold = fields.IntField(default=0, description="Продано МПСтатс+Вайлдберрис")
    mpstats_maniplace_sold = fields.IntField(default=0, description="Продано МПСтатс+Маниплейс")
    
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "daily_metrics"
        unique_together = ("manager", "date")

    def __str__(self):
        return f"Metrics {self.manager.full_name} - {self.date}"

    @classmethod
    async def get_or_create_today(cls, manager: Manager) -> "DailyMetrics":
        """Получить или создать метрики на сегодня"""
        today = date.today()
        metrics, created = await cls.get_or_create(
            manager=manager,
            date=today
        )
        return metrics

    def to_export_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для экспорта в Google Sheets"""
        return {
            "Менеджер": self.manager.full_name,
            "Дата": self.date.strftime("%Y-%m-%d"),
            "К-во диалогов всего за день": self.total_dialogs,
            "К-во новых клиентов": self.new_clients,
            "К-во активных клиентов": self.active_clients,
            "К-во новичков написало": self.newcomers_contacted,
            "К-во новичков купило": self.newcomers_purchased,
            "К-во разослано сообщений о продлении": self.renewal_messages_sent,
            "К-во клиентов продлило": self.clients_renewed,
            "К-во отказов": self.rejections,
            "К-во смс старичкам без ответа": self.sms_silent_clients,
            "К-во выдано бонусов": self.bonuses_given,
            "К-во получено отзывов за день от клиентов": self.reviews_received,
            "Фактическая выручка за день": self.total_revenue,
            "Фактическая выручка по новичкам": self.newcomer_revenue,
            "Мпстатс": self.mpstats_sold,
            "Вайлдбокс": self.wildberries_sold,
            "Маркетгуру": self.marketguru_sold,
            "Маниплейс": self.maniplace_sold,
            "Мпстатс+маркетуру": self.mpstats_marketguru_sold,
            "Мпстатс+вайлдбокс": self.mpstats_wildberries_sold,
            "Мпстатс+маниплейс": self.mpstats_maniplace_sold,
        }


class Transaction(Model):
    """Транзакция - отдельное действие менеджера"""
    id = fields.IntField(pk=True)
    manager = fields.ForeignKeyField("models.Manager", related_name="transactions")
    date = fields.DatetimeField(auto_now_add=True)
    
    # Исходные данные
    raw_message = fields.TextField(description="Исходное сообщение менеджера")
    
    # Распарсенные данные
    action_type = fields.CharField(max_length=50, description="Тип действия")
    client_name = fields.CharField(max_length=100, null=True, description="Имя клиента")
    is_new_client = fields.BooleanField(null=True, description="Новый клиент?")
    products = fields.JSONField(default=list, description="Список продуктов")
    amount = fields.FloatField(null=True, description="Сумма сделки")
    count = fields.IntField(default=1, description="Количество действий")
    
    # Дополнительные данные
    parsed_data = fields.JSONField(default=dict, description="Полные данные парсинга")
    processed = fields.BooleanField(default=False, description="Обработано в метриках?")
    
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "transactions"

    def __str__(self):
        return f"Transaction: {self.action_type} by {self.manager.full_name}"

    @property
    def products_list(self) -> list:
        """Список продуктов как Python список"""
        if isinstance(self.products, str):
            try:
                return json.loads(self.products)
            except json.JSONDecodeError:
                return []
        return self.products or []


# Константы для типов действий
class ActionType:
    NEW_PURCHASE = "new_purchase"
    RENEWAL = "renewal"
    REJECTION = "rejection"
    BONUS = "bonus"
    REVIEW = "review"
    CONTACT = "contact"
    SMS = "sms"
    RENEWAL_MESSAGE = "renewal_message"
    DIALOG = "dialog"

    ALL_TYPES = [
        NEW_PURCHASE, RENEWAL, REJECTION, BONUS, 
        REVIEW, CONTACT, SMS, RENEWAL_MESSAGE, DIALOG
    ]


# Константы для продуктов
class ProductType:
    MPSTATS = "mpstats"
    WILDBERRIES = "wildberries"
    MARKETGURU = "marketguru"
    MANIPLACE = "maniplace"

    ALL_PRODUCTS = [MPSTATS, WILDBERRIES, MARKETGURU, MANIPLACE]
    
    # Связки продуктов
    COMBO_MPSTATS_MARKETGURU = "mpstats+marketguru"
    COMBO_MPSTATS_WILDBERRIES = "mpstats+wildberries"
    COMBO_MPSTATS_MANIPLACE = "mpstats+maniplace"
    
    ALL_COMBOS = [
        COMBO_MPSTATS_MARKETGURU,
        COMBO_MPSTATS_WILDBERRIES,
        COMBO_MPSTATS_MANIPLACE
    ]
