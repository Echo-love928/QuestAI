from dataclasses import dataclass, field

from app.core.exceptions import ResearchBudgetExceeded


@dataclass
class ResearchBudget:
    max_tool_calls: int
    max_search_calls: int
    max_extract_urls: int
    tool_calls: int = 0
    search_calls: int = 0
    extracted_urls: set[str] = field(default_factory=set)

    def _claim_tool(self) -> None:
        if self.tool_calls >= self.max_tool_calls:
            raise ResearchBudgetExceeded("已达到本次资料获取调用上限")
        self.tool_calls += 1

    def claim_search(self) -> None:
        if self.search_calls >= self.max_search_calls:
            raise ResearchBudgetExceeded("已达到本次搜索调用上限")
        self._claim_tool()
        self.search_calls += 1

    def claim_extract(self, urls: list[str]) -> None:
        unique = set(urls)
        if len(self.extracted_urls | unique) > self.max_extract_urls:
            raise ResearchBudgetExceeded("已达到本次网页提取数量上限")
        self._claim_tool()
        self.extracted_urls.update(unique)
