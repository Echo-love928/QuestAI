from datetime import datetime
from hashlib import sha256
import ipaddress
from urllib.parse import urlsplit, urlunsplit

from app.core.exceptions import EvidenceInsufficient, TopicAmbiguous
from app.research.models import AcquisitionMethod, EvidenceSource, ResearchBrief


def restrict_brief_to_known_sources(
    brief: ResearchBrief, sources: list[EvidenceSource]
) -> ResearchBrief:
    """Drop model-generated source references that were not collected."""
    available_ids = {source.source_id for source in sources}
    key_facts = []
    for fact in brief.key_facts:
        known_ids = [
            source_id for source_id in fact.source_ids if source_id in available_ids
        ]
        if known_ids:
            key_facts.append(fact.model_copy(update={"source_ids": known_ids}))
    return brief.model_copy(
        update={
            "key_facts": key_facts,
            "first_party_source_ids": [
                source_id
                for source_id in brief.first_party_source_ids
                if source_id in available_ids
            ],
        }
    )


def canonicalize_source_url(value: str) -> str | None:
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    host = parts.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return None
    try:
        if not ipaddress.ip_address(host).is_global:
            return None
    except ValueError:
        pass
    default_port = (parts.scheme.lower() == "https" and port == 443) or (
        parts.scheme.lower() == "http" and port == 80
    )
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]" if port is None or default_port else f"[{host}]:{port}"
    else:
        netloc = host if port is None or default_port else f"{host}:{port}"
    return urlunsplit(
        (parts.scheme.lower(), netloc, parts.path or "/", parts.query, "")
    )


def validate_research_brief(
    brief: ResearchBrief, sources: list[EvidenceSource]
) -> None:
    if brief.is_ambiguous:
        raise TopicAmbiguous("主题含义仍不明确，请补充所属领域")
    available_ids = {source.source_id for source in sources}
    cited_ids = {
        source_id for fact in brief.key_facts for source_id in fact.source_ids
    }
    first_party_ids = set(brief.first_party_source_ids)
    site_names = {source.site_name for source in sources}
    has_source_support = bool(first_party_ids & available_ids) or len(site_names) >= 2
    if (
        not brief.is_sufficient
        or not sources
        or not brief.key_facts
        or not cited_ids
        or not cited_ids.issubset(available_ids)
        or not first_party_ids.issubset(available_ids)
        or not has_source_support
    ):
        raise EvidenceInsufficient("现有资料不足以可靠生成题目")


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class EvidenceCollector:
    def __init__(self, *, max_total_chars: int, max_source_chars: int = 8_000):
        self.max_total_chars = max_total_chars
        self.max_source_chars = max_source_chars
        self._sources: dict[str, EvidenceSource] = {}
        self.truncated_chars = 0

    @property
    def sources(self) -> list[EvidenceSource]:
        return list(self._sources.values())

    @property
    def methods(self) -> set[AcquisitionMethod]:
        return {source.acquisition_method for source in self._sources.values()}

    @property
    def accepted_chars(self) -> int:
        return sum(len(source.content) for source in self._sources.values())

    def _upsert(
        self,
        item: dict,
        *,
        method: AcquisitionMethod,
        content_field: str,
    ) -> EvidenceSource | None:
        url = canonicalize_source_url(str(item.get("url") or ""))
        content = " ".join(str(item.get(content_field) or "").split())
        if not url or not content:
            return None
        existing = self._sources.get(url)
        occupied = sum(
            len(source.content)
            for key, source in self._sources.items()
            if key != url
        )
        allowed = min(self.max_source_chars, max(0, self.max_total_chars - occupied))
        if allowed == 0:
            return None
        if len(content) > allowed:
            self.truncated_chars += len(content) - allowed
        content = content[:allowed]
        host = urlsplit(url).hostname or "unknown"
        title = str(item.get("title") or "").strip()
        if existing:
            title = existing.title if not title else title
            if method == "search_snippet" and existing.acquisition_method != method:
                return existing
            if (
                method == "search_snippet"
                and existing.acquisition_method == "search_snippet"
                and existing.score is not None
                and float(item.get("score") or 0) <= existing.score
            ):
                return existing
        source = EvidenceSource(
            source_id=f"src_{sha256(url.encode('utf-8')).hexdigest()[:12]}",
            title=title or host,
            url=url,
            site_name=host,
            acquisition_method=method,
            published_at=_published_at(
                item.get("published_at") or item.get("published_date")
            ),
            content=content,
            score=float(item["score"]) if item.get("score") is not None else None,
        )
        self._sources[url] = source
        return source

    def add_search(self, raw: dict) -> list[EvidenceSource]:
        added: dict[str, EvidenceSource] = {}
        for item in raw.get("results") or []:
            if not isinstance(item, dict) or not str(item.get("title") or "").strip():
                continue
            source = self._upsert(
                item, method="search_snippet", content_field="content"
            )
            if source:
                added[source.source_id] = source
        return list(added.values())

    def add_extract(
        self, raw: dict, *, user_urls: set[str]
    ) -> list[EvidenceSource]:
        normalized_user_urls = {
            value for url in user_urls if (value := canonicalize_source_url(url))
        }
        added: dict[str, EvidenceSource] = {}
        for item in raw.get("results") or []:
            if not isinstance(item, dict):
                continue
            url = canonicalize_source_url(str(item.get("url") or ""))
            method: AcquisitionMethod = (
                "user_url_extract"
                if url in normalized_user_urls
                else "search_result_extract"
            )
            source = self._upsert(item, method=method, content_field="raw_content")
            if source:
                added[source.source_id] = source
        return list(added.values())
