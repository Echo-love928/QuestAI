from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


SearchDepth = Literal["basic", "advanced", "fast", "ultra-fast"]
SearchTopic = Literal["general", "news", "finance"]
TimeRange = Literal["day", "week", "month", "year"]
Complexity = Literal["simple", "complex"]
ExtractDepth = Literal["basic", "advanced"]
AcquisitionMethod = Literal[
    "search_snippet", "user_url_extract", "search_result_extract", "private_document"
]
GroundingMode = Literal["user_content", "web_search", "url_extract", "mixed", "private", "hybrid"]
SourceKind = Literal["web", "private_document"]


class SearchToolInput(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    complexity: Complexity = "simple"
    search_depth: SearchDepth = "basic"
    max_results: int = Field(default=3, ge=3, le=20)
    chunks_per_source: int = Field(default=1, ge=1, le=3)
    topic: SearchTopic = "general"
    time_range: TimeRange | None = None
    country: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=40)
    filter_by_language: bool = False
    include_domains: list[str] = Field(default_factory=list, max_length=5)
    exclude_domains: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class ExtractToolInput(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)
    extract_depth: ExtractDepth = "basic"
    query: str | None = Field(default=None, max_length=500)
    chunks_per_source: int = Field(default=3, ge=1, le=5)

    @field_validator("urls")
    @classmethod
    def unique_urls(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class QuizSource(BaseModel):
    source_id: str
    title: str
    url: str
    site_name: str
    acquisition_method: AcquisitionMethod
    published_at: datetime | None = None
    source_type: SourceKind = "web"
    knowledge_base_id: int | None = None
    document_id: str | None = None
    location: str | None = None


class EvidenceSource(QuizSource):
    content: str
    score: float | None = None

    def to_public(self) -> QuizSource:
        return QuizSource.model_validate(
            self.model_dump(exclude={"content", "score"})
        )

    def to_agent(self) -> dict:
        return self.model_dump(mode="json", exclude={"score", "published_at"})


class ResearchFact(BaseModel):
    text: str = Field(min_length=2, max_length=1000)
    source_ids: list[str] = Field(min_length=1, max_length=8)


class ResearchBrief(BaseModel):
    resolved_topic: str = Field(min_length=2, max_length=200)
    domain: str = Field(min_length=2, max_length=160)
    is_ambiguous: bool
    is_sufficient: bool
    summary: str = Field(min_length=2, max_length=2000)
    key_facts: list[ResearchFact] = Field(default_factory=list, max_length=20)
    first_party_source_ids: list[str] = Field(default_factory=list, max_length=8)


class ResearchResult(BaseModel):
    grounding_mode: GroundingMode
    brief: ResearchBrief | None = None
    sources: list[EvidenceSource] = Field(default_factory=list)
    researched_at: datetime | None = None
