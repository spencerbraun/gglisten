"""AI text processing using Claude via litellm"""

import instructor
import litellm
from pydantic import BaseModel, Field

from ..config import get_config


class CleanedText(BaseModel):
    """Cleaned up text output"""

    text: str = Field(
        description="The cleaned up text with filler words removed and grammar fixed"
    )


def get_client():
    """Get instructor client for structured outputs"""
    return instructor.from_litellm(litellm.completion)


def clean_text(text: str, model: str | None = None) -> str:
    """
    Clean up transcribed text using AI.

    Removes filler words, fixes grammar, improves clarity
    while preserving the original meaning and voice.
    """
    config = get_config()
    api_key = config.get_anthropic_key()

    if not api_key:
        raise ValueError(
            f"Anthropic API key not found. Create file at {config.anthropic_key_file}"
        )

    if model is None:
        model = config.default_model

    client = get_client()

    result = client.chat.completions.create(
        model=model,
        api_key=api_key,
        response_model=CleanedText,
        messages=[
            {
                "role": "system",
                "content": """You are a text cleanup assistant. Your job is to take voice transcriptions
and clean them up while preserving the original meaning and voice.

Clean up the text by:
- Removing filler words (um, uh, like, you know, so, basically)
- Fixing grammar and punctuation
- Improving sentence structure for clarity
- Removing false starts and repetitions

Keep:
- The original meaning and intent
- The speaker's voice and style
- All important details and information
- First person perspective if present

Return ONLY the cleaned text, nothing else.""",
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        max_tokens=4096,
    )

    return result.text


def process_for_email(text: str, model: str | None = None) -> str:
    """Format transcribed text as a professional email"""
    config = get_config()
    api_key = config.get_anthropic_key()

    if not api_key:
        raise ValueError(f"Anthropic API key not found")

    if model is None:
        model = config.default_model

    client = get_client()

    result = client.chat.completions.create(
        model=model,
        api_key=api_key,
        response_model=CleanedText,
        messages=[
            {
                "role": "system",
                "content": """Convert this voice transcription into a professional email.

- Use appropriate greeting and sign-off
- Organize content clearly with paragraphs
- Maintain a professional but friendly tone
- Keep the key points and requests
- Fix any grammar or clarity issues

Return ONLY the email text, ready to send.""",
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        max_tokens=4096,
    )

    return result.text
