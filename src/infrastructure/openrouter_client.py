import asyncio
import aiohttp
import json
import logging
from src.core.interfaces import IAIAnalyzer

_RETRY_ATTEMPTS = 3
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class OpenRouterAnalyzer(IAIAnalyzer):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def analyze_urgency(self, subject: str, text: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        truncated_text = text[:2000]

        prompt = (
            "Ты — профессиональный секретарь-ассистент студента и сотрудника университета. "
            "Твоя задача: критически оценить входящее письмо и определить, требует ли оно СРОЧНОГО действия "
            "в рамках учебного или рабочего процесса.\n\n"
            
            "КРИТЕРИИ ВАЖНОСТИ (is_important: true):\n"
            "- Адресные уведомления о записи на курсы/события с ограниченным числом мест.\n"
            "- Личные вызовы: деканат, руководство, медосмотр, студенты, приглашение на собеседование.\n"
            "- Письма о критических дедлайнах по проектам, документам или оплате обучения.\n"
            "- Информация об изменениях в расписании или месте проведения встреч.\n\n"
            
            "КРИТЕРИИ ИГНОРИРОВАНИЯ (is_important: false):\n"
            "- МАРКЕТИНГОВАЯ СРОЧНОСТЬ: Любые призывы купить, записаться на скидку или вебинар.\n"
            "- РАССЫЛКИ: Массовые дайджесты, новости индустрии, приглашения на общие мероприятия.\n"
            "- СПАМ И РЕКЛАМА: Предложения услуг, даже если они выглядят как 'важное уведомление'.\n"
            "- Отсутствие персонального обращения или четкого требования к действию.\n\n"
            
            "МЕТОДИКА АНАЛИЗА:\n"
            "1. Проверь отправителя и контекст: это администрация/коллега или коммерческий сервис?\n"
            "2. Отличи учебный дедлайн от рекламного предложения.\n"
            "3. Если сомневаешься — помечай как false. Лучше пропустить письмо, чем отвлечь пользователя спамом.\n\n"
            
            f"Тема: {subject}\n"
            f"Текст: {truncated_text}\n\n"
            "Ответь СТРОГО в формате JSON без markdown и лишнего текста.\n"
            "Поле reason пиши СТРОГО на русском языке.\n"
            '{"is_important": true/false, "reason": "Краткая причина (до 20 слов), почему это критично или почему проигнорировано."}'
        )
        """
        prompt = (
            "Ты — ИИ-ассистент студента/сотрудника. Твоя задача — анализировать входящие email-письма "
            "и определять, требуют ли они НЕМЕДЛЕННОЙ реакции или являются критически важными.\n"
            "Критерии ВАЖНОГО письма:\n"
            "- Запись на курсы/мероприятия с ограниченным количеством мест.\n"
            "- Срочные вызовы (деканат, руководство, медосмотр).\n"
            "- Горящие дедлайны по сдаче важных проектов/документов.\n\n"
            "НЕ ВАЖНЫЕ письма (игнорируй их):\n"
            "- Информационные рассылки, новости, дайджесты.\n"
            "- Реклама, спам, приглашения на необязательные вебинары.\n\n"
            f"Тема письма: {subject}\n"
            f"Текст письма: {truncated_text}\n\n"
            "Ответь строго в формате JSON без markdown и лишнего текста.\n"
            "Поле reason пиши СТРОГО на русском языке.\n"
            '{"is_important": true/false, "reason": "Краткая выжимка на русском: почему это важно или почему нет. До 15 слов."}'
        )
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        logging.info(f"🤖 [OpenRouter] -> Отправляем письмо: '{subject}' (текст: {truncated_text[:50]}...)")

        last_error = None
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            for attempt in range(_RETRY_ATTEMPTS):
                try:
                    async with session.post(self.url, headers=headers, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            content = data['choices'][0]['message']['content'].strip()

                            logging.info(f"🤖 [OpenRouter] <- Ответ: {content}")

                            try:
                                if content.startswith("```json"):
                                    content = content[7:-3].strip()
                                elif content.startswith("```"):
                                    content = content[3:-3].strip()

                                result = json.loads(content)
                                return {
                                    "is_important": bool(result.get("is_important", False)),
                                    "reason": str(result.get("reason", "Не удалось извлечь причину."))
                                }
                            except json.JSONDecodeError:
                                logging.error(f"❌ [OpenRouter] Ошибка парсинга JSON! Сырой ответ: {content}")
                                return {"is_important": False, "reason": "Ошибка парсинга ответа AI."}
                        else:
                            error_text = await response.text()
                            logging.error(f"❌ [OpenRouter] Ошибка API (попытка {attempt + 1}): {response.status} - {error_text}")
                            last_error = f"HTTP {response.status}"
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logging.warning(f"⚠️ [OpenRouter] Сетевая ошибка (попытка {attempt + 1}): {e}")
                    last_error = str(e)

                if attempt < _RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(2 ** attempt)

        logging.error(f"❌ [OpenRouter] Все {_RETRY_ATTEMPTS} попытки исчерпаны. Последняя ошибка: {last_error}")
        return {"is_important": False, "reason": "Сервис AI недоступен."}
