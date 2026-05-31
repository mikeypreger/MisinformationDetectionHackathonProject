# pipeline/caption_extractor.py
# Requires: python -m spacy download en_core_web_sm
import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

load_dotenv()

_nlp = None
_gemini_model = None
_query_cache: dict[str, list[str]] = {}  # caption → queries; avoids duplicate API calls
_TARGET_ENTS = {"PERSON", "ORG", "GPE", "LOC", "EVENT", "DATE", "FAC", "NORP"}

# Words that correspond to visually observable things in a photograph.
# Used when GPT is unavailable to build specific image search queries.
_VISUAL_NOUNS = {
    # Physical states / casualties
    "corpse", "corpses", "body", "bodies", "dead", "wounded", "injured",
    "victim", "victims", "survivor", "survivors", "casualty", "casualties",
    # People / roles
    "soldier", "soldiers", "officer", "protester", "protesters", "crowd",
    "civilian", "civilians", "refugee", "refugees", "child", "children",
    # Objects
    "phone", "gun", "weapon", "weapons", "knife", "bomb", "rocket", "missile",
    "flag", "sign", "banner", "car", "truck", "tank",
    # Actions (visually observable)
    "texting", "shooting", "running", "marching", "crying", "holding",
    "carrying", "burning", "rallying", "protesting",
    # Scene / setting
    "explosion", "fire", "smoke", "rubble", "ruins", "hospital", "ambulance",
    "funeral", "shroud", "wrapped", "cloth", "burial", "mosque", "church",
    "street", "building", "crowd",
}

_GPT_SYSTEM = """\
You are a Google Image search query generator for a misinformation detection system.
Given a social media caption, generate exactly 3 search queries that would find
news photos VISUALLY ILLUSTRATING the event or subject described.

Rules:
- Focus on what a photograph of this would look like, not the text itself
- Include the subject's name + their sport/domain/role where applicable
- Avoid queries about contracts, salaries, or text-only topics
- Each query should be 3-7 words
- Rank queries from most to least specific: Q1 is the most targeted (names + context),
  Q2 is action/scene focused, Q3 is the broadest useful fallback

Return JSON: {"queries": ["query1", "query2", "query3"]}

Example:
Caption: "OFFICIAL: Bulls sign Adama Sanogo to two-way contract."
Output: {"queries": ["Adama Sanogo Chicago Bulls basketball", "NBA player basketball court action", "Chicago Bulls forward game photo"]}

Example:
Caption: "In an apparent miracle, corpses in Gaza are seen texting their loved ones."
Output: {"queries": ["Gaza corpse person phone", "wrapped body holding phone", "Gaza burial white cloth"]}
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
    """Extract named entities from caption to provide GPT with context."""
    nlp = _load_spacy()
    if nlp is None:
        return []
    doc = nlp(caption)
    return [ent.text.strip() for ent in doc.ents if ent.label_ in _TARGET_ENTS]


def _nlp_visual_queries(caption: str, entities: list[str]) -> list[str]:
    """
    Build specific visual image search queries using spaCy entities and
    a curated visual noun vocabulary — no API required.

    Strategy:
      Q1: "{location} {visual_noun_1} {visual_noun_2}"  (most specific)
      Q2: "{visual_noun_1} {visual_noun_2} photo"       (action/object focused)
      Q3: "{location}" or "{main_entity}"               (broad fallback)
    """
    words_lower = caption.lower().split()
    found_visual = [w.rstrip(".,!?;:") for w in words_lower
                    if w.rstrip(".,!?;:") in _VISUAL_NOUNS]

    # Separate location/place entities from person/org entities
    nlp = _load_spacy()
    locations, others = [], []
    if nlp and entities:
        doc = nlp(caption)
        ent_map = {ent.text: ent.label_ for ent in doc.ents}
        for e in entities:
            if ent_map.get(e) in ("GPE", "LOC", "FAC"):
                locations.append(e)
            else:
                others.append(e)
    else:
        others = entities[:]

    queries = []

    # Q1: location + two visual nouns (or location + entity)
    if locations and len(found_visual) >= 2:
        queries.append(f"{locations[0]} {found_visual[0]} {found_visual[1]}"[:80])
    elif locations and found_visual:
        subject = others[0] if others else found_visual[0]
        queries.append(f"{locations[0]} {subject}"[:80])
    elif others and found_visual:
        queries.append(f"{others[0]} {found_visual[0]}"[:80])

    # Q2: visual nouns + "photo" (no location noise)
    if len(found_visual) >= 2:
        queries.append(f"{found_visual[0]} {found_visual[1]} photo"[:80])
    elif found_visual and (locations or others):
        anchor = locations[0] if locations else others[0]
        queries.append(f"{anchor} {found_visual[0]} photo"[:80])

    # Q3: broadest useful signal
    if locations:
        queries.append(locations[0])
    elif others:
        queries.append(others[0])
    elif found_visual:
        queries.append(found_visual[0])

    # Deduplicate and ensure at least one query
    seen, unique = set(), []
    for q in queries:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            unique.append(q)

    return unique[:3] if unique else [caption[:60]]

def _gemini_queries(caption: str, entities: list[str]) -> list[str] | None:
    global _gemini_model
    if _gemini_model is None:
        # 1. Ensure API_KEY is set. For Free tier, use key from aistudio.google.com
        api_key = os.getenv("GOOGLE_API_KEY")
        
        # 2. Use the standard client which defaults to the AI Studio endpoints
        client = genai.Client(api_key=api_key)
        _gemini_model = (client, genai_types)

    client, types = _gemini_model

    user_msg = caption
    if entities:
        user_msg += f"\n\n[Detected entities: {', '.join(entities)}]"

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=_GPT_SYSTEM,
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        
        # Safe JSON parsing
        data = json.loads(resp.text)
        
        if isinstance(data, list):
            return [str(q) for q in data[:3]]
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    return [str(q) for q in val[:3]]
                    
        return None
    except Exception as e:
        print(f"[caption_extractor] Gemini API Error: {e}")
        return None

def extract_search_queries(caption: str, post_url: str = "") -> list[str]:
    """
    Returns 3 Google Image search queries that visually describe the caption.
    Results are cached by caption text — Gemini is called at most once per unique caption.
    1. Return cached result if available
    2. Try Gemini Flash (best quality, visual queries)
    3. If Gemini fails: use spaCy entities + visual noun vocabulary (no API)
    4. Last resort: truncated caption
    """
    if not caption or not caption.strip():
        return [post_url[:80]] if post_url else [""]

    cache_key = caption.strip()
    if cache_key in _query_cache:
        print("[caption_extractor] cache hit — skipping Gemini call")
        return _query_cache[cache_key]

    entities = _spacy_entities(caption)

    gemini_result = _gemini_queries(caption, entities)
    result = gemini_result if gemini_result else _nlp_visual_queries(caption, entities)

    _query_cache[cache_key] = result
    return result