#!/usr/bin/env python3
"""
Скрипт для тестирования основных функций бота
"""
import asyncio
import json
import sys
from datetime import date

# Добавляем путь к модулям
sys.path.insert(0, '.')

from config import config
from models import Manager, DailyMetrics, Transaction, ActionType
from gpt_parser import gpt_parser
from metrics_service import metrics_service
from google_sheets_service import google_sheets_service
from tortoise import Tortoise


class BotTester:
    """Класс для тестирования функций бота"""
    
    def __init__(self):
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Логирование результата теста"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   └─ {details}")
        
        self.test_results.append({
            "name": test_name,
            "success": success,
            "details": details
        })
    
    async def init_test_db(self):
        """Инициализация тестовой базы данных"""
        try:
            await Tortoise.init(
                db_url="sqlite://test_db.sqlite3",
                modules={'models': ['models']}
            )
            await Tortoise.generate_schemas()
            self.log_test("Инициализация БД", True)
        except Exception as e:
            self.log_test("Инициализация БД", False, str(e))
            raise
    
    async def test_config_loading(self):
        """Тест загрузки конфигурации"""
        try:
            # Проверяем основные поля
            required_fields = [
                'telegram_token', 'admin_chat_id', 'openai_token',
                'google_credentials_file', 'google_sheet_id'
            ]
            
            missing_fields = []
            for field in required_fields:
                if not hasattr(config, field) or not getattr(config, field):
                    missing_fields.append(field)
            
            if missing_fields:
                self.log_test("Загрузка конфигурации", False, f"Отсутствуют поля: {missing_fields}")
            else:
                self.log_test("Загрузка конфигурации", True, "Все обязательные поля присутствуют")
                
        except Exception as e:
            self.log_test("Загрузка конфигурации", False, str(e))
    
    async def test_gpt_parser(self):
        """Тест GPT парсера"""
        test_messages = [
            {
                "text": "Новый клиент Иван купил mpstats за 2000р",
                "expected_action": "new_purchase",
                "expected_amount": 2000,
                "expected_products": ["mpstats"]
            },
            {
                "text": "Продлил Петров wildberries + marketguru, 3500р",
                "expected_action": "renewal",
                "expected_amount": 3500,
                "expected_products": ["wildberries", "marketguru"]
            },
            {
                "text": "Отказ от Сидорова",
                "expected_action": "rejection",
                "expected_amount": None,
                "expected_products": []
            }
        ]
        
        success_count = 0
        
        for i, test_case in enumerate(test_messages):
            try:
                result = await gpt_parser.parse_message(test_case["text"])
                
                if result:
                    # Проверяем основные поля
                    checks = [
                        result.get("action_type") == test_case["expected_action"],
                        result.get("amount") == test_case["expected_amount"],
                        set(result.get("products", [])) == set(test_case["expected_products"])
                    ]
                    
                    if all(checks):
                        success_count += 1
                        self.log_test(f"GPT парсер #{i+1}", True, f"Корректно распарсил: {test_case['text'][:30]}...")
                    else:
                        self.log_test(f"GPT парсер #{i+1}", False, f"Неверный результат для: {test_case['text'][:30]}...")
                else:
                    self.log_test(f"GPT парсер #{i+1}", False, f"Нет результата для: {test_case['text'][:30]}...")
                    
            except Exception as e:
                self.log_test(f"GPT парсер #{i+1}", False, f"Ошибка: {e}")
        
        overall_success = success_count == len(test_messages)
        self.log_test("GPT парсер (общий)", overall_success, f"Успешно: {success_count}/{len(test_messages)}")
    
    async def test_database_operations(self):
        """Тест операций с базой данных"""
        try:
            # Создание тестового менеджера
            test_manager = await Manager.create(
                telegram_user_id=12345,
                full_name="Тестовый Менеджер",
                username="test_manager"
            )
            
            self.log_test("Создание менеджера", True, f"ID: {test_manager.id}")
            
            # Создание метрик
            metrics = await DailyMetrics.get_or_create_today(test_manager)
            
            # Обновление метрик
            metrics.new_clients += 1
            metrics.total_revenue += 1000
            await metrics.save()
            
            self.log_test("Работа с метриками", True, "Создание и обновление")
            
            # Создание транзакции
            transaction = await Transaction.create(
                manager=test_manager,
                raw_message="Тестовое сообщение",
                action_type=ActionType.NEW_PURCHASE,
                amount=1000,
                products=["mpstats"]
            )
            
            self.log_test("Создание транзакции", True, f"ID: {transaction.id}")
            
        except Exception as e:
            self.log_test("Операции с БД", False, str(e))
    
    async def test_metrics_service(self):
        """Тест сервиса метрик"""
        try:
            # Получаем тестового менеджера
            manager = await Manager.get_or_none(telegram_user_id=12345)
            if not manager:
                self.log_test("Сервис метрик", False, "Тестовый менеджер не найден")
                return
            
            # Тестируем обработку сообщения
            result = await metrics_service.process_manager_message(
                manager, 
                "Новый клиент Анна купила mpstats за 1500р"
            )
            
            if result["success"]:
                self.log_test("Обработка сообщения", True, "Сообщение обработано успешно")
                
                # Проверяем статистику
                stats = await metrics_service.get_manager_stats_today(manager)
                
                if stats["new_clients"] > 0:
                    self.log_test("Обновление статистики", True, f"Новых клиентов: {stats['new_clients']}")
                else:
                    self.log_test("Обновление статистики", False, "Статистика не обновилась")
            else:
                self.log_test("Обработка сообщения", False, result.get("error", "Неизвестная ошибка"))
                
        except Exception as e:
            self.log_test("Сервис метрик", False, str(e))
    
    async def test_google_sheets_connection(self):
        """Тест подключения к Google Sheets"""
        try:
            # Проверяем подключение
            connection_ok = await google_sheets_service.check_connection()
            
            if connection_ok:
                self.log_test("Подключение к Google Sheets", True, "Соединение установлено")
                
                # Пробуем получить последнюю дату экспорта
                last_date = await google_sheets_service.get_last_export_date()
                self.log_test("Чтение данных из Sheets", True, f"Последняя дата: {last_date or 'Нет данных'}")
                
            else:
                self.log_test("Подключение к Google Sheets", False, "Не удалось установить соединение")
                
        except Exception as e:
            self.log_test("Google Sheets", False, str(e))
    
    async def test_export_functionality(self):
        """Тест функции экспорта"""
        try:
            # Получаем метрики за сегодня
            all_metrics = await metrics_service.get_all_managers_metrics_today()
            
            if not all_metrics:
                self.log_test("Экспорт данных", False, "Нет данных для экспорта")
                return
            
            # Пробуем экспортировать (в тестовом режиме можно закомментировать)
            # success = await google_sheets_service.export_daily_metrics(all_metrics)
            # 
            # if success:
            #     self.log_test("Экспорт в Google Sheets", True, f"Экспортировано записей: {len(all_metrics)}")
            # else:
            #     self.log_test("Экспорт в Google Sheets", False, "Ошибка экспорта")
            
            # Для тестирования просто проверяем формат данных
            export_data = all_metrics[0].to_export_dict()
            
            if len(export_data) > 10:  # Проверяем количество полей
                self.log_test("Формат экспорта", True, f"Полей для экспорта: {len(export_data)}")
            else:
                self.log_test("Формат экспорта", False, "Недостаточно полей для экспорта")
                
        except Exception as e:
            self.log_test("Экспорт данных", False, str(e))
    
    async def cleanup_test_data(self):
        """Очистка тестовых данных"""
        try:
            # Удаляем тестовые данные
            test_manager = await Manager.get_or_none(telegram_user_id=12345)
            if test_manager:
                await test_manager.delete()
            
            await Tortoise.close_connections()
            
            # Удаляем тестовую БД
            import os
            if os.path.exists("test_db.sqlite3"):
                os.remove("test_db.sqlite3")
            
            self.log_test("Очистка тестовых данных", True)
            
        except Exception as e:
            self.log_test("Очистка тестовых данных", False, str(e))
    
    def print_summary(self):
        """Вывод итогов тестирования"""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["success"])
        failed = total - passed
        
        print("\n" + "="*70)
        print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
        print("="*70)
        print(f"Всего тестов: {total}")
        print(f"✅ Успешно: {passed}")
        print(f"❌ Неудачно: {failed}")
        print(f"📈 Процент успеха: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\n🚨 Неудачные тесты:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  • {result['name']}: {result['details']}")
        
        print("="*70)
        
        return failed == 0


async def main():
    """Главная функция тестирования"""
    print("🧪 Запуск тестирования бота для учета метрик продаж")
    print("="*70)
    
    tester = BotTester()
    
    try:
        # Инициализация
        await tester.init_test_db()
        
        # Основные тесты
        await tester.test_config_loading()
        await tester.test_gpt_parser()
        await tester.test_database_operations()
        await tester.test_metrics_service()
        await tester.test_google_sheets_connection()
        await tester.test_export_functionality()
        
    except Exception as e:
        print(f"❌ Критическая ошибка тестирования: {e}")
        return False
    
    finally:
        # Очистка
        await tester.cleanup_test_data()
    
    # Итоги
    success = tester.print_summary()
    
    if success:
        print("\n🎉 Все тесты прошли успешно! Бот готов к работе.")
        return True
    else:
        print("\n⚠️ Некоторые тесты не прошли. Проверьте конфигурацию и исправьте ошибки.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Фатальная ошибка: {e}")
        sys.exit(1)
