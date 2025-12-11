"""Azure OpenAI Voice client for audio generation."""

import base64
from typing import Optional

from openai import AsyncAzureOpenAI

from ..config.settings import get_azure_openai_settings

# Singleton instance
_voice_client: Optional["AzureOpenAIVoiceClient"] = None


class AzureOpenAIVoiceClient:
    """Client for generating audio using Azure OpenAI gpt-4o-audio-preview model."""

    AVAILABLE_VOICES = [
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "marin",
        "sage",
        "shimmer",
        "verse",
        "cedar",
    ]

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-10-21",
    ):
        """Initialize the voice client.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            deployment: Model deployment name (gpt-4o-audio-preview)
            api_version: API version to use
        """
        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self.deployment = deployment

    async def generate_audio(
        self,
        system_prompt: str,
        user_content: str,
        voice: str = "marin",
        audio_format: str = "mp3",
    ) -> tuple[bytes, str]:
        """Generate audio and transcript from prompt.

        Args:
            system_prompt: System instructions for the model
            user_content: User message (typically JSON data to narrate)
            voice: Voice to use (marin, cedar, alloy, etc.)
            audio_format: Audio format (mp3, wav, etc.)

        Returns:
            Tuple of (audio_bytes, transcript_text)
        """
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            modalities=["text", "audio"],
            audio={"voice": voice, "format": audio_format},
        )

        # Extract audio data and transcript from response
        audio_data = response.choices[0].message.audio
        audio_b64 = audio_data.data
        transcript = audio_data.transcript

        # Decode base64 audio to bytes
        audio_bytes = base64.b64decode(audio_b64)

        return audio_bytes, transcript


def get_openai_voice_client() -> AzureOpenAIVoiceClient:
    """Get cached AzureOpenAIVoiceClient instance (singleton).

    Returns:
        Configured voice client
    """
    global _voice_client
    if _voice_client is None:
        settings = get_azure_openai_settings()
        _voice_client = AzureOpenAIVoiceClient(
            api_key=settings.api_key,
            endpoint=settings.endpoint,
            deployment=settings.deployment_name,
            api_version=settings.api_version,
        )
    return _voice_client
