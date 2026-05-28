# pipeline/caption_extractor.py
# Requires: python -m spacy download en_core_web_sm
import os
import json
from dotenv import load_dotenv

load_dotenv()

_nlp = None
_openai_client = None
_TARGET_ENTS = {"PERSON", "ORG", "GPE", "LOC", "EVENT", "DATE", "FAC", "NORP"}

_GPT_SYSTEM = """\
You are a Google Image search query generator for a misinformation detection system.
Given a social media caption, generate exactly 3 search queries that would find
news photos VISUALLY ILLUSTRATING the event or subject described.

Rules:
- Focus on what a photograph of this would look like, not the text itself
- Include the subject's name + their sport/domain/role where applicable
- Queries should retrieve diverse but contextually relevant photos
- Avoid queries about contracts, salaries, or text-only topics
- Each query should be 3-7 words

Return JSON: {"queries": ["query1", "query2", "query3"]}

Example:
Caption: "OFFICIAL: We have signed Adama Sanogo to a Two-Way contract."
Output: {"queries": ["Adama Sanogo Chicago Bulls basketball", "NBA player basketball court action", "Chicago Bulls forward game photo"]}
"""


def _load_spacy():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            _nlp = None
    return _nlp


def _spacy_entities(caption: str) -> list[str]:
    """Extract named entities from caption to give GPT useful context."""
    nlp = _load_spacy()
    if nlp is None:
        return []
    doc = nlp(caption)
    return [ent.text.strip() for ent in doc.ents if ent.label_ in _TARGET_ENTS]


def _gpt_queries(caption: str, entities: list[str]) -> list[str]:
    """
    Use GPT-4o-mini to generate visually-descriptive image search queries.
    entities: named entities pre-extracted by spaCy, passed as context.
    """
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Enrich the user message with extracted entities so GPT doesn't have to guess
    user_msg = caption
    if entities:
        user_msg += f"\n\n[Detected entities: {', '.join(entities)}]"

    try:
        resp = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _GPT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        # Accept {"queries": [...]} or any key whose value is a list
        if isinstance(data, list):
            return [str(q) for q in data[:3]]
        for val in data.values():
            if isinstance(val, list):
                return [str(q) for q in val[:3]]
        print(f"[caption_extractor] GPT unexpected structure: {data}")
    except Exception as e:
        print(f"[caption_extractor] GPT failed ({type(e).__name__}): {e}")

    # Last resort: use spaCy entities if available, else truncated caption
    if entities:
        return [" ".join(entities[:3])[:60]]
    return [caption[:60]] if caption.strip() else [""]


def extract_search_queries(caption: str, post_url: str = "") -> list[str]:
    """
    Returns 3 Google Image search queries that visually describe the caption.
    Always uses GPT (with spaCy entities as context). Falls back gracefully.
    """
    if not caption or not caption.strip():
        return [post_url[:80]] if post_url else [""]

    entities = _spacy_entities(caption)
    return _gpt_queries(caption, entities)
