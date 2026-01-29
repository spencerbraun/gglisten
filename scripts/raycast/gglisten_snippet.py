#!/usr/bin/env -S /Users/spencerbraun/.cargo/bin/uv run --script

# @raycast.title gGlisten Snippet
# @raycast.mode compact
# @raycast.schemaVersion 1
# @raycast.icon 📝

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "litellm",
#     "instructor",
#     "pydantic",
# ]
# ///

"""
Voice snippet capture: reads latest gGlisten transcription,
extracts date + content via LLM, appends to snippets file.
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

import instructor
import litellm

# Add gglisten to path
GGLISTEN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(GGLISTEN_ROOT))

from gglisten import storage

# Config
SNIPPETS_DIR = Path("/Users/spencerbraun/Documents/Notes/Content/Snippets")
MODEL = "anthropic/claude-sonnet-4-5-20250929"

# API key: read from file
API_KEY_FILE = Path.home() / ".config" / "gglisten_anthropic_key"
if not API_KEY_FILE.exists():
    # Fall back to old location
    API_KEY_FILE = Path.home() / ".config" / "snippet_anthropic_key"
API_KEY = API_KEY_FILE.read_text().strip() if API_KEY_FILE.exists() else None


class DaySnippet(BaseModel):
    """Snippet for a single day"""
    date: str = Field(
        description="Date in YYYY-MM-DD format. "
        "Extract from speech (e.g. 'yesterday', 'Monday', 'December 10th')."
    )
    bullets: list[str] = Field(
        description="Bullet points for this day. "
        "Clean up speech disfluencies, make concise but preserve detail. "
        "Keep first person."
    )


class Snippet(BaseModel):
    """Structured snippet output - can contain multiple days"""
    days: list[DaySnippet] = Field(
        description="List of day snippets. Group bullets by the date they refer to. "
        "If no date is mentioned, use today's date. "
        "If multiple dates are mentioned, create separate entries for each."
    )


def get_clipboard():
    """Get clipboard contents"""
    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
    return result.stdout.strip()


def get_latest_gglisten_transcription(max_age_seconds=600):
    """Get the most recent gGlisten transcription (within max_age_seconds)"""
    latest = storage.get_latest()
    if not latest:
        return None

    age = datetime.now().timestamp() - latest.timestamp
    if age > max_age_seconds:
        return None

    return latest.text


def parse_snippet(text: str) -> Snippet:
    """Use LLM to extract structured snippet from voice transcription"""
    today = datetime.now()

    if not API_KEY:
        raise ValueError("API key not set. Create ~/.config/gglisten_anthropic_key")

    client = instructor.from_litellm(litellm.completion)

    return client.chat.completions.create(
        model=MODEL,
        response_model=Snippet,
        api_key=API_KEY,
        messages=[
            {
                "role": "system",
                "content": f"""You are helping convert voice transcriptions into daily work snippets.

Today is {today.strftime('%A, %B %d, %Y')}.

Your job is to take my spoken words and clean them up into bullet points while keeping
most everything I said. Preserve the detail, context, and my voice. Just:
- Remove filler words (um, uh, like, you know)
- Fix grammar and sentence structure
- Split into logical bullet points
- Keep first person

Don't summarize aggressively or remove information. If I said it, it should be in there
in some form.

For dates: extract from speech if mentioned (e.g. "yesterday", "Monday", "December 10th").
Calculate the actual YYYY-MM-DD date. Default to today if no date mentioned.
The date is the header, so do not include the date in the bullet points.
For day names, use the most recent past occurrence.

IMPORTANT: I may describe multiple days in one recording. Group bullets by the day they
refer to. Create separate day entries for each date mentioned. Days can be in any order."""
            },
            {
                "role": "user",
                "content": text
            }
        ],
        max_tokens=10000,
    )


def format_date_header(date_str: str) -> str:
    """Convert YYYY-MM-DD to 'Weekday, Month Day, Year'"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%A, %B %d, %Y").replace(" 0", " ")


def get_snippets_file(date_str: str) -> Path:
    """Get the snippets file for a given date's year"""
    year = date_str[:4]
    return SNIPPETS_DIR / f"Snippets {year}.md"


def parse_existing_dates(content: str) -> list[tuple[str, int, int]]:
    """Parse existing date headers, return list of (date_str, start_line, end_line)"""
    lines = content.split('\n')
    dates = []

    date_pattern = re.compile(r'^## (\w+), (\w+) (\d+), (\d+)$')

    for i, line in enumerate(lines):
        match = date_pattern.match(line)
        if match:
            weekday, month, day, year = match.groups()
            try:
                dt = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
                date_str = dt.strftime("%Y-%m-%d")
                dates.append((date_str, i))
            except ValueError:
                continue

    # Calculate end lines
    result = []
    for i, (date_str, start) in enumerate(dates):
        if i + 1 < len(dates):
            end = dates[i + 1][1] - 1
        else:
            end = len(lines) - 1
        result.append((date_str, start, end))

    return result


def update_snippets_file(file_path: Path, date_str: str, bullets: list[str]):
    """Update snippets file with new content for a date"""
    date_header = f"## {format_date_header(date_str)}"
    bullet_text = '\n'.join(f"- {b}" for b in bullets)

    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"{date_header}\n{bullet_text}\n", encoding='utf-8')
        return

    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    existing_dates = parse_existing_dates(content)

    for existing_date, start_line, end_line in existing_dates:
        if existing_date == date_str:
            insert_line = start_line + 1
            for i in range(start_line + 1, end_line + 1):
                if lines[i].startswith('- '):
                    insert_line = i + 1
                elif lines[i].strip() == '' and i > start_line + 1:
                    break

            for j, bullet in enumerate(bullets):
                lines.insert(insert_line + j, f"- {bullet}")

            file_path.write_text('\n'.join(lines), encoding='utf-8')
            return

    insert_position = 0
    for existing_date, start_line, _ in existing_dates:
        if date_str > existing_date:
            insert_position = start_line
            break
        insert_position = start_line

    if existing_dates and date_str < existing_dates[-1][0]:
        insert_position = len(lines)

    new_section = [date_header, bullet_text, '']

    for i, line in enumerate(new_section):
        lines.insert(insert_position + i, line)

    file_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    # Try gGlisten database first (last 10 min), fall back to clipboard
    text = get_latest_gglisten_transcription(max_age_seconds=600)
    source = "gGlisten"

    if not text:
        text = get_clipboard()
        source = "clipboard"

    if not text:
        print("No transcription found (gGlisten or clipboard)")
        return

    if len(text) < 10:
        print("Text too short")
        return

    try:
        snippet = parse_snippet(text)
    except Exception as e:
        print(f"LLM error: {e}")
        return

    if not snippet.days:
        print("No content extracted")
        return

    total_bullets = 0
    dates_updated = []

    for day in snippet.days:
        if not day.bullets:
            continue

        file_path = get_snippets_file(day.date)
        update_snippets_file(file_path, day.date, day.bullets)
        total_bullets += len(day.bullets)
        dates_updated.append(format_date_header(day.date))

    if len(dates_updated) == 1:
        print(f"Added {total_bullets} bullets to {dates_updated[0]}")
    else:
        print(f"Added {total_bullets} bullets across {len(dates_updated)} days")


if __name__ == "__main__":
    main()
