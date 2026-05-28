# pipeline/caption_extractor.py
import os
import json
from dotenv import load_dotenv

load_dotenv()

_nlp = None
_TARGET_ENTS = {"PERSON", "ORG", "GPE", "LOC", "EVENT", "DATE", "FAC", "NORP"}

def _load_spacy():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            _nlp = None
    return _nlp

def _nlp_queries(caption: str) -> list[str] | None:
    nlp = _load_spacy()
    if nlp is None:
        return None

    doc = nlp(caption)
    entities = [ent.text.strip() for ent in doc.ents if ent.label_ in _TARGET_ENTS]
    noun_chunks = [chunk.text.strip() for chunk in doc.noun_chunks if len(chunk.text.split()) >= 2]

    if len(entities) < 1:
        return None

    primary = " ".join(entities[:3])[:80]
    queries = [primary]

    # CLEAN PARSING: Prevent "Adama Sanogo Adama Sanogo" repetition loops
    entity_texts_lower = {e.lower() for e in entities}

    for chunk in noun_chunks:
        chunk_lower = chunk.lower()
        # Ensure noun chunk doesn't overlap or duplicate known named entities
        if not any(e in chunk_lower or chunk_lower in e for e in entity_texts_lower):
            secondary = f"{entities[0]} {chunk}"[:80]
            if secondary not in queries:
                queries.append(secondary)
            break

    return queries[:2] if queries else None

def extract_search_queries(caption: str, post_url: str = "") -> list[str]:
    if not caption or not caption.strip():
        return [post_url[:80]] if post_url else [""]
    
    queries = _nlp_queries(caption)
    if queries:
        return queries
        
    # Last resort fallback if spaCy yields nothing
    return [caption[:60]] if caption.strip() else [""]