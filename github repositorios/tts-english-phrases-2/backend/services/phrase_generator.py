import json
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

client = AsyncOpenAI()


def calc_num_phrases(duration_minutes: int) -> int:
    base = max(1, round(duration_minutes * 60 / 9))
    return round(base * 1.2)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def generate_phrases(language: str, topic: str, num_phrases: int) -> list[str]:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a language learning content creator specializing in comprehensible input. "
                    f"Generate exactly {num_phrases} simple, natural spoken phrases in {language} about the topic: '{topic}'. "
                    f"Requirements:\n"
                    f"- Each phrase must be 6-12 words long\n"
                    f"- Use natural conversational language (not textbook formal)\n"
                    f"- Appropriate for intermediate learners\n"
                    f"- Varied sentence structures\n"
                    f"- Relevant vocabulary for the topic\n"
                    f"Return ONLY a JSON array of strings, no other text. Example: [\"phrase one\", \"phrase two\"]"
                ),
            },
            {
                "role": "user",
                "content": f"Generate {num_phrases} {language} phrases about: {topic}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)

    if isinstance(parsed, list):
        phrases = parsed
    elif isinstance(parsed, dict):
        phrases = next(iter(parsed.values()))
    else:
        raise ValueError(f"Unexpected GPT response format: {type(parsed)}")

    if not isinstance(phrases, list) or len(phrases) == 0:
        raise ValueError("GPT returned empty or invalid phrase list")

    return [str(p).strip() for p in phrases if str(p).strip()]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def interpret_topic(topic: str, language: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful language learning assistant. "
                    "When given a topic and target language, describe in 1-2 sentences "
                    "what kind of phrases you would generate for a learner. Be specific and encouraging."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"I'm learning {language} and I want to practice: '{topic}'. "
                    f"What kind of phrases would you generate for me?"
                ),
            },
        ],
        temperature=0.7,
        max_tokens=150,
    )

    return response.choices[0].message.content.strip()
