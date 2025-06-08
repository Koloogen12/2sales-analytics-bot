"""
Конфигурация бота для автоматического сбора метрик продаж
"""
import json
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Config:
    # Telegram
    telegram_token: str = "7893115588:AAHhmTSQrtZHZWWFdYsYnazRnDpwXMNA0M0"
    admin_chat_id: int = 889614996
    
    # OpenAI
    openai_token: str =  "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"
    openai_model: str = "gpt-4"
    
    # Google Sheets
    google_credentials_file: str = "credentials.json"
    google_sheet_id: str = "1lwcmOgViDgKTY_lyMpkO3wqfMigLPo1PKZj_gyXPF64"
    google_sheet_name: str = "Лист"
    
    # Планировщик
    daily_export_time: str = "23:55"  # HH:MM
    
    # База данных
    database_url: str = "sqlite://db.sqlite3"
    
    # Режим отладки
    debug: bool = False

    @classmethod
    def load_from_file(cls, config_path: str = "config.json") -> "Config":
        """Загрузка конфигурации из JSON файла"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"❌ Файл конфигурации '{config_path}' не найден")
            
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return cls(
            telegram_token=data["telegram_token"],
            admin_chat_id=data["admin_chat_id"],
            openai_token=data["openai_token"],
            openai_model=data.get("openai_model", "gpt-4"),
            google_credentials_file=data["google_credentials_file"],
            google_sheet_id=data["google_sheet_id"],
            google_sheet_name=data.get("google_sheet_name", "Метрики продаж"),
            daily_export_time=data.get("daily_export_time", "23:55"),
            database_url=data.get("database_url", "sqlite://db.sqlite3"),
            debug=data.get("debug", False)
        )
    
    def validate(self) -> None:
        """Валидация конфигурации"""
        required_fields = [
            "telegram_token", "admin_chat_id", "openai_token",
            "google_credentials_file", "google_sheet_id"
        ]
        
        for field in required_fields:
            if not getattr(self, field):
                raise ValueError(f"❌ Обязательное поле '{field}' не заполнено")
        
        if not os.path.exists(self.google_credentials_file):
            raise FileNotFoundError(f"❌ Файл Google credentials '{self.google_credentials_file}' не найден")
        
        # Проверка формата времени
        try:
            hour, minute = map(int, self.daily_export_time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError:
            raise ValueError(f"❌ Неверный формат времени: {self.daily_export_time}. Используйте HH:MM")


# Создание глобального экземпляра конфигурации
config = Config.load_from_file()
config.validate()

print("✅ Конфигурация загружена и проверена")
print(f"🤖 Telegram Token: {config.telegram_token[:10]}...")
print(f"📊 Google Sheet ID: {config.google_sheet_id}")
print(f"🧠 OpenAI Model: {config.openai_model}")
print(f"🕒 Время экспорта: {config.daily_export_time}")
print(f"🔧 Режим отладки: {config.debug}")
