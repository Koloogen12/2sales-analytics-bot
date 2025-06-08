"""
Сервис для парсинга сообщений менеджеров через GPT
"""
import json
import logging
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI, OpenAIError

from config import config
from models import ActionType, ProductType

logger = logging.getLogger(__name__)


class GPTParser:
    """Парсер сообщений менеджеров через OpenAI GPT"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai_token)
        
    def _get_parsing_prompt(self) -> str:
        """Получить промпт для парсинга сообщений"""
        return f"""
Ты - AI-парсер сообщений менеджера по продажам. 
Твоя задача: извлечь из сообщения данные и вернуть ТОЛЬКО валидный JSON.

Возможные типы действий (action_type):
- "new_purchase": новая покупка от нового клиента
- "renewal": продление/покупка от существующего клиента  
- "rejection": отказ клиента от покупки
- "bonus": выдача бонуса клиенту
- "review": получение отзыва от клиента
- "contact": контакт с новичком (без покупки)
- "sms": отправка СМС молчунам/старичкам
- "renewal_message": отправка сообщения о продлении
- "dialog": просто диалог/общение

Возможные продукты:
- "mpstats" (мпстатс, mpstats)
- "wildberries" (вайлдберрис, вб, wb, wildberries)  
- "marketguru" (маркетгуру, маркет гуру, marketguru)
- "maniplace" (маниплейс, маниплэйс, maniplace)

Связки продуктов определяй как массив: ["mpstats", "marketguru"]

Формат ответа (ТОЛЬКО JSON, без комментариев):
{{
  "action_type": "тип_действия",
  "client_name": "имя клиента или null",
  "is_new_client": true/false/null,
  "products": ["список", "продуктов"],
  "amount": число_или_null,
  "count": количество_действий_по_умолчанию_1,
  "confidence": число_от_0_до_1
}}

Примеры:

"Новый клиент Иван купил мпстатс за 2000р"
{{"action_type": "new_purchase", "client_name": "Иван", "is_new_client": true, "products": ["mpstats"], "amount": 2000, "count": 1, "confidence": 0.95}}

"Продлил Петров вайлдберрис + маркетгуру, 3500р"
{{"action_type": "renewal", "client_name": "Петров", "is_new_client": false, "products": ["wildberries", "marketguru"], "amount": 3500, "count": 1, "confidence": 0.9}}

"Отказ от Сидорова, не подошла цена"
{{"action_type": "rejection", "client_name": "Сидорова", "is_new_client": null, "products": [], "amount": null, "count": 1, "confidence": 0.85}}

"Выдал бонус 500р клиенту Козлову"
{{"action_type": "bonus", "client_name": "Козлову", "is_new_client": null, "products": [], "amount": 500, "count": 1, "confidence": 0.9}}

"Получил отзыв от Андреева - очень доволен"
{{"action_type": "review", "client_name": "Андреева", "is_new_client": null, "products": [], "amount": null, "count": 1, "confidence": 0.85}}

"Написал 5 новичкам"
{{"action_type": "contact", "client_name": null, "is_new_client": true, "products": [], "amount": null, "count": 5, "confidence": 0.8}}

"Разослал сообщения о продлении 10 клиентам"
{{"action_type": "renewal_message", "client_name": null, "is_new_client": false, "products": [], "amount": null, "count": 10, "confidence": 0.9}}

"СМС отправил 3 молчунам"
{{"action_type": "sms", "client_name": null, "is_new_client": null, "products": [], "amount": null, "count": 3, "confidence": 0.85}}

Сообщение для анализа:
"""

    async def parse_message(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг сообщения менеджера через GPT
        
        Args:
            message: Сообщение менеджера
            
        Returns:
            Словарь с распарсенными данными или None при ошибке
        """
        try:
            prompt = self._get_parsing_prompt()
        
        # ВЫВОД КЛЮЧА
        print("OPENAI_API_KEY:", config.openai_token)
        
            response = await self.client.chat.completions.create(
                model=config.openai_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,  # Низкая температура для точности
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Попытка парсинга JSON
            try:
                parsed_data = json.loads(result_text)
            except json.JSONDecodeError:
                # Если GPT вернул не чистый JSON, пытаемся извлечь его
                import re
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    parsed_data = json.loads(json_match.group())
                else:
                    logger.error(f"Не удалось извлечь JSON из ответа GPT: {result_text}")
                    return None
            
            # Валидация и нормализация данных
            validated_data = self._validate_parsed_data(parsed_data)
            
            logger.info(f"Успешно распарсено сообщение: {message[:50]}...")
            logger.info(f"Результат: {validated_data}")
            
            return validated_data
            
        except OpenAIError as e:
            logger.error(f"Ошибка OpenAI API: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при парсинге: {e}")
            return None
    
    def _validate_parsed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидация и нормализация распарсенных данных
        
        Args:
            data: Сырые данные от GPT
            
        Returns:
            Валидированные данные
        """
        # Проверка action_type
        action_type = data.get("action_type", "dialog")
        if action_type not in ActionType.ALL_TYPES:
            logger.warning(f"Неизвестный action_type: {action_type}, используем 'dialog'")
            action_type = "dialog"
        
        # Нормализация продуктов
        products = data.get("products", [])
        if not isinstance(products, list):
            products = []
        
        normalized_products = []
        for product in products:
            normalized_product = self._normalize_product_name(str(product).lower())
            if normalized_product:
                normalized_products.append(normalized_product)
        
        # Валидация суммы
        amount = data.get("amount")
        if amount is not None:
            try:
                amount = float(amount)
                if amount < 0:
                    amount = None
            except (ValueError, TypeError):
                amount = None
        
        # Валидация количества
        count = data.get("count", 1)
        try:
            count = int(count)
            if count < 1:
                count = 1
        except (ValueError, TypeError):
            count = 1
        
        # Валидация confidence
        confidence = data.get("confidence", 0.5)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5
        
        return {
            "action_type": action_type,
            "client_name": data.get("client_name"),
            "is_new_client": data.get("is_new_client"),
            "products": normalized_products,
            "amount": amount,
            "count": count,
            "confidence": confidence
        }
    
    def _normalize_product_name(self, product: str) -> Optional[str]:
        """
        Нормализация названия продукта
        
        Args:
            product: Название продукта в любом формате
            
        Returns:
            Стандартизированное название или None
        """
        product = product.lower().strip()
        
        # Мпстатс
        if any(word in product for word in ["мпстатс", "mpstats", "мп статс"]):
            return ProductType.MPSTATS
        
        # Вайлдберрис
        if any(word in product for word in ["вайлдберрис", "wildberries", "вб", "wb", "вайлд"]):
            return ProductType.WILDBERRIES
        
        # Маркетгуру
        if any(word in product for word in ["маркетгуру", "marketguru", "маркет гуру", "гуру"]):
            return ProductType.MARKETGURU
        
        # Маниплейс
        if any(word in product for word in ["маниплейс", "maniplace", "маниплэйс", "мани"]):
            return ProductType.MANIPLACE
        
        logger.warning(f"Неизвестный продукт: {product}")
        return None

    def format_confirmation(self, parsed_data: Dict[str, Any]) -> str:
        """
        Форматирование подтверждения для пользователя
        
        Args:
            parsed_data: Распарсенные данные
            
        Returns:
            Строка подтверждения
        """
        action_type = parsed_data.get("action_type", "")
        client_name = parsed_data.get("client_name", "")
        amount = parsed_data.get("amount")
        products = parsed_data.get("products", [])
        count = parsed_data.get("count", 1)
        confidence = parsed_data.get("confidence", 0)
        
        # Эмодзи для типов действий
        action_emojis = {
            "new_purchase": "🆕",
            "renewal": "🔄", 
            "rejection": "❌",
            "bonus": "🎁",
            "review": "⭐",
            "contact": "📞",
            "sms": "📱",
            "renewal_message": "📧",
            "dialog": "💬"
        }
        
        # Названия действий
        action_names = {
            "new_purchase": "Новая покупка",
            "renewal": "Продление",
            "rejection": "Отказ",
            "bonus": "Бонус",
            "review": "Отзыв",
            "contact": "Контакт",
            "sms": "СМС",
            "renewal_message": "Сообщение о продлении",
            "dialog": "Диалог"
        }
        
        emoji = action_emojis.get(action_type, "📝")
        action_name = action_names.get(action_type, action_type)
        
        parts = [f"{emoji} {action_name}"]
        
        if client_name:
            parts.append(f"👤 Клиент: {client_name}")
        
        if products:
            product_names = {
                "mpstats": "МПСтатс",
                "wildberries": "Вайлдберрис", 
                "marketguru": "Маркетгуру",
                "maniplace": "Маниплейс"
            }
            formatted_products = [product_names.get(p, p) for p in products]
            parts.append(f"📦 Продукты: {', '.join(formatted_products)}")
        
        if amount:
            parts.append(f"💰 Сумма: {amount:,.0f}₽")
        
        if count > 1:
            parts.append(f"🔢 Количество: {count}")
        
        # Показываем уверенность только если она низкая
        if confidence < 0.7:
            parts.append(f"⚠️ Уверенность: {confidence:.0%}")
        
        return "\n".join(parts)


# Глобальный экземпляр парсера
gpt_parser = GPTParser()
