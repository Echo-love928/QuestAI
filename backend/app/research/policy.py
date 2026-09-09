import re
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.quiz import QuizGenerateRequest


URL_PATTERN = re.compile(r"https?://[^\s<>\]\[\"']+", re.IGNORECASE)
TEMPORAL_PATTERN = re.compile(
    r"最新|当前|近期|最近|现在|今日|本周|本月|版本|release|latest|current|recent|today|20\d{2}",
    re.IGNORECASE,
)


class InputKind(StrEnum):
    TOPIC = "topic"
    MATERIAL = "material"
    URL = "url"
    MIXED = "mixed"


class InputDecision(BaseModel):
    kind: InputKind
    requires_research: bool
    urls: list[str] = Field(default_factory=list)
    has_temporal_intent: bool = False


def classify_input(
    request: QuizGenerateRequest, *, full_material_min_chars: int
) -> InputDecision:
    text = request.user_input.strip()
    urls = URL_PATTERN.findall(text)
    temporal = bool(TEMPORAL_PATTERN.search(text))
    if request.source_type == "url" or (len(urls) == 1 and urls[0] == text):
        return InputDecision(
            kind=InputKind.URL,
            requires_research=True,
            urls=urls or [text],
            has_temporal_intent=temporal,
        )
    if urls:
        return InputDecision(
            kind=InputKind.MIXED,
            requires_research=True,
            urls=urls,
            has_temporal_intent=temporal,
        )
    kind = InputKind.MATERIAL if len(text) >= full_material_min_chars else InputKind.TOPIC
    return InputDecision(
        kind=kind,
        requires_research=kind == InputKind.TOPIC or temporal,
        has_temporal_intent=temporal,
    )


def localize_query(
    original: str,
    *,
    english_term: str | None = None,
    city: str | None = None,
    country: str | None = None,
) -> str:
    parts: list[str] = []
    for value in (original, english_term, city, country):
        cleaned = " ".join((value or "").split())
        if cleaned and cleaned.casefold() not in {item.casefold() for item in parts}:
            parts.append(cleaned)
    return " ".join(parts)
