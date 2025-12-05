"""OpenAI Whisper transcription service for voice messages."""

import httpx

from src.config import settings


class TranscriptionService:
    """Service for transcribing audio/video using OpenAI Whisper API."""

    WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"

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
