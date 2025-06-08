#!/bin/bash

# Скрипт деплоя Telegram бота для учета метрик продаж
# Использование: ./deploy.sh [production|development]

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для цветного вывода
error() { echo -e "${RED}❌ $1${NC}" >&2; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️ $1${NC}"; }

# Проверка аргументов
ENVIRONMENT=${1:-development}
if [[ "$ENVIRONMENT" != "production" && "$ENVIRONMENT" != "development" ]]; then
    error "Неверный аргумент. Используйте: production или development"
    exit 1
fi

info "Запуск деплоя в режиме: $ENVIRONMENT"

# Проверка зависимостей
check_dependencies() {
    info "Проверка зависимостей..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker не установлен"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose не установлен"
        exit 1
    fi
    
    success "Все зависимости установлены"
}

# Проверка конфигурационных файлов
check_config() {
    info "Проверка конфигурации..."
    
    if [[ ! -f "config.json" ]]; then
        error "Файл config.json не найден"
        info "Скопируйте config.json.example в config.json и заполните"
        exit 1
    fi
    
    if [[ ! -f "credentials.json" ]]; then
        error "Файл credentials.json не найден"
        info "Получите credentials.json из Google Cloud Console"
        exit 1
    fi
    
    # Проверка обязательных полей в config.json
    if ! grep -q "YOUR_" config.json; then
        success "Конфигурация заполнена"
    else
        warning "В config.json остались примеры значений (YOUR_*)"
        warning "Убедитесь, что все поля заполнены правильно"
    fi
}

# Создание необходимых директорий
create_directories() {
    info "Создание директорий..."
    
    mkdir -p data logs backup
    
    # Установка правильных разрешений
    chmod 755 data logs backup
    
    success "Директории созданы"
}

# Бэкап данных (только для production)
backup_data() {
    if [[ "$ENVIRONMENT" == "production" && -f "data/db.sqlite3" ]]; then
        info "Создание бэкапа данных..."
        
        BACKUP_FILE="backup/db_$(date +%Y%m%d_%H%M%S).sqlite3"
        cp data/db.sqlite3 "$BACKUP_FILE"
        
        success "Бэкап создан: $BACKUP_FILE"
    fi
}

# Остановка старых контейнеров
stop_containers() {
    info "Остановка старых контейнеров..."
    
    if docker-compose ps | grep -q "sales-metrics-bot"; then
        docker-compose down
        success "Старые контейнеры остановлены"
    else
        info "Запущенных контейнеров не найдено"
    fi
}

# Сборка и запуск
build_and_start() {
    info "Сборка и запуск контейнеров..."
    
    # Сборка образа
    docker-compose build --no-cache
    
    # Запуск в зависимости от окружения
    if [[ "$ENVIRONMENT" == "production" ]]; then
        docker-compose up -d
    else
        # В development режиме показываем логи
        docker-compose up -d
        info "Контейнеры запущены в development режиме"
        info "Для просмотра логов: docker-compose logs -f"
    fi
    
    success "Контейнеры запущены"
}

# Проверка здоровья
health_check() {
    info "Проверка состояния контейнеров..."
    
    # Ждем 10 секунд для инициализации
    sleep 10
    
    # Проверка статуса контейнера
    if docker-compose ps | grep -q "Up"; then
        success "Контейнер запущен успешно"
        
        # Проверка здоровья
        info "Ожидание завершения инициализации..."
        sleep 10
        
        HEALTH_STATUS=$(docker inspect sales-metrics-bot --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-health")
        
        if [[ "$HEALTH_STATUS" == "healthy" ]]; then
            success "Проверка здоровья прошла успешно"
        elif [[ "$HEALTH_STATUS" == "starting" ]]; then
            warning "Контейнер все еще инициализируется"
            info "Проверьте статус позже: docker inspect sales-metrics-bot"
        else
            warning "Health check недоступен или не настроен"
        fi
        
    else
        error "Контейнер не запущен"
        info "Проверьте логи: docker-compose logs sales-metrics-bot"
        exit 1
    fi
}

# Вывод информации о деплое
deployment_info() {
    info "Информация о деплое:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Деплой завершен успешно!"
    echo ""
    echo "📊 Статус сервисов:"
    docker-compose ps
    echo ""
    echo "📋 Полезные команды:"
    echo "  Логи:           docker-compose logs -f sales-metrics-bot"
    echo "  Остановка:      docker-compose down"
    echo "  Перезапуск:     docker-compose restart sales-metrics-bot"
    echo "  Статус:         docker-compose ps"
    echo "  Статистика:     docker stats sales-metrics-bot"
    echo ""
    echo "🔗 Файлы:"
    echo "  Конфигурация:   ./config.json"
    echo "  База данных:    ./data/db.sqlite3"
    echo "  Логи:           ./logs/"
    echo "  Бэкапы:         ./backup/"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Функция очистки (для development)
cleanup() {
    if [[ "$ENVIRONMENT" == "development" ]]; then
        echo ""
        warning "Для полной очистки используйте:"
        echo "  docker-compose down --volumes --rmi all"
        echo "  rm -rf data/* logs/*"
    fi
}

# Главная функция
main() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🤖 Деплой Telegram бота для учета метрик продаж"
    echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
    echo "🔧 Окружение: $ENVIRONMENT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Выполнение этапов деплоя
    check_dependencies
    check_config
    create_directories
    backup_data
    stop_containers
    build_and_start
    health_check
    deployment_info
    cleanup
    
    echo ""
    success "Деплой завершен успешно! 🎉"
}

# Обработка сигналов
trap 'error "Деплой прерван пользователем"; exit 1' INT TERM

# Запуск
main "$@"