"""OpenAI Whisper transcription service for voice messages."""

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for transcribing audio/video using OpenAI Whisper API."""

    WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"
    CHAT_API_URL = "https://api.openai.com/v1/chat/completions"

    FORMAT_PROMPT = """Ты помощник для форматирования транскрибированного текста.

Твоя задача - взять сырой текст из голосовой транскрибации и сделать его читаемым:

1. Раздели текст на логические абзацы по смыслу
2. Исправь пунктуацию (точки, запятые, вопросительные знаки)
3. Используй Markdown форматирование где уместно:
   - **жирный** для важных слов/фраз
   - Списки (- или 1.) если перечисляются пункты
   - > цитаты если есть прямая речь
4. Начинай предложения с заглавной буквы

ВАЖНО:
- НЕ меняй смысл и идею текста
- НЕ перефразируй - сохраняй оригинальные слова автора
- НЕ добавляй свои мысли, комментарии или заключения
- НЕ добавляй заголовки если их не было в речи
- Просто структурируй и форматируй то что есть

Верни ТОЛЬКО отформатированный текст, без пояснений."""

    async def transcribe_bytes(
        self,
        content: bytes,
        filename: str,
        language: str = "ru",
    ) -> str:
        """
        Transcribe audio/video from bytes using OpenAI Whisper API.

        Args:
            content: Raw bytes of audio/video file
            filename: Filename with extension (e.g., "voice.ogg", "video.mp4")
            language: Language code for better accuracy (default: "ru")

        Returns:
            Transcribed text

        Raises:
            ValueError: If OpenAI API key is not configured
            httpx.HTTPStatusError: If API request fails
        """
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.WHISPER_API_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                files={"file": (filename, content)},
                data={"model": "whisper-1", "language": language},
                timeout=120.0,  # Voice notes can be long
            )

            response.raise_for_status()
            return response.json()["text"]

    async def format_transcription(self, raw_text: str) -> str:
        """
        Format transcribed text using GPT-4o-mini for better readability.

        Args:
            raw_text: Raw text from Whisper transcription

        Returns:
            Formatted text with proper structure and punctuation
        """
        if not raw_text or not raw_text.strip():
            return raw_text

        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured, skipping formatting")
            return raw_text

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.CHAT_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": self.FORMAT_PROMPT},
                            {"role": "user", "content": raw_text},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 4000,
                    },
                    timeout=60.0,
                )

                response.raise_for_status()
                result = response.json()
                formatted_text = result["choices"][0]["message"]["content"]
                return formatted_text.strip()

        except Exception as e:
            logger.error(f"Failed to format transcription: {e}")
            return raw_text
