# 🤖 Telegram Bot для учета метрик продаж

Автоматизированная система учета метрик продаж через Telegram бота с использованием GPT для парсинга естественного языка и автоматическим экспортом в Google Sheets.

## 🚀 Возможности

### Автоматический сбор метрик
- **Естественный язык**: Менеджеры описывают действия обычным текстом
- **GPT-парсинг**: Автоматическое извлечение данных из сообщений
- **20+ метрик**: Полный набор KPI для отдела продаж

### Отслеживаемые метрики
- Количество диалогов всего за день
- Количество новых/активных клиентов
- Количество новичков (написало/купило)
- Сообщения о продлении и продления
- Отказы и бонусы
- Получение отзывов
- Выручка (общая и по новичкам)
- Продажи по продуктам и связкам

### Автоматизация
- **Ежедневный экспорт** в Google Sheets в 23:55
- **Напоминания** менеджерам за 30 минут до экспорта
- **Еженедельная аналитика** каждое воскресенье
- **Уведомления** о статусе системы

## 📋 Требования

### Системные требования
- Python 3.11+
- Docker & Docker Compose (для контейнеризации)
- 512MB RAM
- 1GB свободного места

### API ключи
- **Telegram Bot Token** - создать через @BotFather
- **OpenAI API Key** - для GPT-парсинга
- **Google Service Account** - для работы с Google Sheets

## 🛠 Установка и настройка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd sales-metrics-bot
```

### 2. Настройка конфигурации

#### Создание config.json
```bash
cp config.json.example config.json
```

Заполните `config.json`:
```json
{
  "telegram_token": "YOUR_BOT_TOKEN",
  "admin_chat_id": 123456789,
  "openai_token": "sk-...",
  "openai_model": "gpt-4",
  "google_credentials_file": "credentials.json",
  "google_sheet_id": "YOUR_SHEET_ID",
  "google_sheet_name": "Метрики продаж",
  "daily_export_time": "23:55",
  "database_url": "sqlite://data/db.sqlite3",
  "debug": false
}
```

#### Настройка Google Sheets
1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com)
2. Включите Google Sheets API
3. Создайте Service Account и скачайте `credentials.json`
4. Создайте Google Таблицу и предоставьте доступ Service Account
5. Скопируйте ID таблицы из URL

### 3. Запуск через Docker (рекомендуется)

```bash
# Создание директорий для данных
mkdir -p data logs

# Размещение конфигурационных файлов
# config.json и credentials.json должны быть в корне проекта

# Запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f sales-metrics-bot

# Остановка
docker-compose down
```

### 4. Запуск без Docker (разработка)

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python main.py
```

## 📱 Использование

### Регистрация менеджера
1. Напишите боту `/start`
2. Используйте `/register`
3. Введите ФИО

### Работа с метриками
Просто описывайте действия естественным языком:

```
Новый клиент Иван купил mpstats за 2000р
Продлил Петров wildberries + marketguru, 3500р
Отказ от Сидорова, не подошла цена
Выдал бонус 500р клиенту Козлову
Получил отзыв от Андреева - очень доволен
Написал 5 новичкам
Разослал сообщения о продлении 10 клиентам
```

### Команды бота
- `/start` - начало работы
- `/help` - справка
- `/register` - регистрация
- `/stats` - статистика за сегодня

### Админские команды
- `/test_export` - тестовый экспорт
- `/reset_stats` - сброс статистики
- `/check_connection` - проверка Google Sheets

## 🔧 Мониторинг и обслуживание

### Логирование
```bash
# Просмотр логов в реальном времени
docker-compose logs -f sales-metrics-bot

# Логи сохраняются в ./logs/
tail -f logs/bot.log
```

### Проверка статуса
```bash
# Статус контейнера
docker-compose ps

# Использование ресурсов
docker stats sales-metrics-bot

# Проверка здоровья
docker inspect sales-metrics-bot | grep Health
```

### Бэкапы
```bash
# Бэкап базы данных
cp data/db.sqlite3 backup/db_$(date +%Y%m%d).sqlite3

# Бэкап конфигурации
tar -czf backup/config_$(date +%Y%m%d).tar.gz config.json credentials.json
```

## 🔒 Безопасность

### Файлы с секретами
- `config.json` - содержит API ключи
- `credentials.json` - Google Service Account
- Не добавляйте в git! Используйте `.gitignore`

### Контейнеризация
- Работает под unprivileged пользователем
- Ограничения ресурсов
- Изолированная сеть

### Мониторинг доступа
- Логирование всех действий
- Уведомления об ошибках
- Автоматическая деактивация заблокировавших бота

## 📊 Структура данных в Google Sheets

Автоматически создаются колонки:
- Дата и Менеджер
- 11 основных метрик (диалоги, клиенты, отказы и т.д.)
- Финансовые показатели (выручка)
- 7 продуктовых метрик (включая связки)

## 🛠 Разработка

### Структура проекта
```
├── main.py                 # Точка входа
├── config.py              # Конфигурация
├── models.py              # Модели БД
├── handlers.py            # Обработчики Telegram
├── gpt_parser.py          # GPT парсер
├── metrics_service.py     # Бизнес-логика метрик
├── google_sheets_service.py # Работа с Google Sheets
├── scheduler.py           # Планировщик задач
├── notification_service.py # Уведомления
├── requirements.txt       # Зависимости
├── Dockerfile            # Контейнеризация
└── docker-compose.yml    # Оркестрация
```

### Добавление новых метрик
1. Обновите модель `DailyMetrics` в `models.py`
2. Добавьте обработку в `MetricsService.update_daily_metrics()`
3. Обновите `DailyMetrics.to_export_dict()`
4. Настройте заголовки в `GoogleSheetsService._setup_header()`

### Улучшение GPT-парсера
1. Обновите промпт в `GPTParser._get_parsing_prompt()`
2. Добавьте новые типы действий в `ActionType`
3. Расширьте валидацию в `GPTParser._validate_parsed_data()`

## 🚨 Решение проблем

### Частые ошибки
1. **Ошибка Google Sheets**: Проверьте права доступа Service Account
2. **GPT не парсит**: Проверьте OpenAI API ключ и баланс
3. **Бот не отвечает**: Проверьте Telegram Bot Token
4. **База данных заблокирована**: Перезапустите контейнер

### Диагностика
```bash
# Проверка подключений
docker exec sales-metrics-bot python -c "
from google_sheets_service import google_sheets_service
import asyncio
print('Sheets:', asyncio.run(google_sheets_service.check_connection()))
"

# Тест GPT
docker exec sales-metrics-bot python -c "
from gpt_parser import gpt_parser
import asyncio
result = asyncio.run(gpt_parser.parse_message('Тест'))
print('GPT:', result)
"
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs sales-metrics-bot`
2. Убедитесь в правильности конфигурации
3. Проверьте доступность API (OpenAI, Google, Telegram)
4. Создайте issue с описанием проблемы и логами

## 📄 Лицензия

MIT License - используйте свободно для коммерческих и некоммерческих целей.
