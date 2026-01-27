"""Processing templates for different use cases"""

TEMPLATES = {
    "clean": """You are a text cleanup assistant. Your job is to take voice transcriptions
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
    "email": """Convert this voice transcription into a professional email.

- Use appropriate greeting and sign-off
- Organize content clearly with paragraphs
- Maintain a professional but friendly tone
- Keep the key points and requests
- Fix any grammar or clarity issues

Return ONLY the email text, ready to send.""",
    "notes": """Convert this voice transcription into organized notes.

- Use bullet points for key items
- Group related information together
- Highlight action items if any
- Keep it concise but complete

Return ONLY the notes, nothing else.""",
    "slack": """Convert this voice transcription into a Slack message.

- Keep it concise and casual
- Use appropriate emoji where natural
- Break into short paragraphs if needed
- Maintain the conversational tone

Return ONLY the message text, nothing else.""",
}


def get_template(name: str) -> str | None:
    """Get a template by name"""
    return TEMPLATES.get(name)


def list_templates() -> list[str]:
    """List available template names"""
    return list(TEMPLATES.keys())
