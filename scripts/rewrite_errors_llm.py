# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "aiohttp",
#     "dotenv",
#     "iofiles",
#     "json",
#     "openai",
# ]
# ///


import asyncio
import getpass
import json
import os
from pathlib import Path

import aiofiles
import aiohttp
from dotenv import load_dotenv
from openai import AsyncOpenAI


def get_openai_api_key() -> str:
    # Try to get the API key from the environment variable
    if api_key := os.getenv("OPENAI_API_KEY"):
        return api_key

    # Load environment variables from a .env file if not already loaded
    load_dotenv()
    if api_key := os.getenv("OPENAI_API_KEY"):
        return api_key

    # Prompt the user for the API key as a last resort
    return getpass.getpass("Enter your OPENAI_API_KEY: ")


# --- Config ---
GUIDELINES_URL = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master/docs/messages-guidelines.md"
INPUT_FILE = "errors.txt"  # Supports either .txt (one per line) or .json (list)
MODEL = "gpt-4"
API_KEY = get_openai_api_key()

client = AsyncOpenAI(api_key=API_KEY)

# --- Functions ---


async def fetch_guidelines() -> str:
    async with aiohttp.ClientSession() as session, session.get(GUIDELINES_URL) as resp:
        return await resp.text()


async def load_messages(filepath: str) -> list[str]:
    path = Path(filepath)
    async with aiofiles.open(path) as f:
        content = await f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return [line.strip() for line in content.splitlines() if line.strip()]


def build_system_prompt(guidelines: str) -> str:
    return f"""
You are a technical writing assistant specialized in crafting professional error and warning messages.
Your task is to rewrite the given error message to strictly adhere to the oSparc Simcore message guidelines.

Here are the guidelines:
{guidelines}

Instructions:
- Follow all the principles from the message guidelines.
- Ensure the message is concise, user-focused, actionable, and avoids developer jargon.
- If there is not enough context, ask a clarifying question.

Use this format only:
If enough context:
REWRITTEN: <rewritten message>
If not enough context:
NEED MORE INFO: <your clarifying question(s)>
""".strip()


async def rewrite_message(message: str, system_prompt: str, index: int) -> dict:
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"ERROR: {message}"},
            ],
            temperature=0,
        )
        return {
            "index": index,
            "original": message,
            "output": response.choices[0].message.content.strip(),
        }
    except Exception as e:
        return {"index": index, "original": message, "error": str(e)}


# --- Main Flow ---


async def main():
    guidelines = await fetch_guidelines()
    system_prompt = build_system_prompt(guidelines)
    messages = await load_messages(INPUT_FILE)

    tasks = [
        rewrite_message(msg, system_prompt, i) for i, msg in enumerate(messages, 1)
    ]
    results = await asyncio.gather(*tasks)

    for result in results:
        print(f"\n[{result['index']}] Original: {result['original']}")
        if "output" in result:
            print(result["output"])
        else:
            print(f"ERROR: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())
