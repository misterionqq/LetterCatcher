import aiohttp
import json
import logging
from src.core.interfaces import IAIAnalyzer

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

        truncated_text = text[:1500]

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
            "Ответь строго в формате JSON без markdown и лишнего текста:\n"
            '{"is_important": true/false, "reason": "Краткая выжимка: почему это важно или почему нет. До 15 слов."}'
        )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        logging.info(f"🤖 [OpenRouter] -> Отправляем письмо: '{subject}' (текст: {truncated_text[:50]}...)")

        connector = aiohttp.TCPConnector(ssl=False) # TODO: удалить из прода))
        async with aiohttp.ClientSession(connector=connector) as session:
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
                        logging.error(f"❌ [OpenRouter] Ошибка API: {response.status} - {error_text}")
                        return {"is_important": False, "reason": "Ошибка сервера AI."}
            except Exception as e:
                logging.error(f"❌ [OpenRouter] Сетевая ошибка: {e}")
                return {"is_important": False, "reason": "Сетевая ошибка."}