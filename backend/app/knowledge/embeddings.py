from __future__ import annotations

from typing import Protocol

from openai import AsyncOpenAI


class EmbeddingError(RuntimeError):
    pass


class EmbeddingGateway(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class BailianEmbeddingGateway:
    def __init__(
        self, *, api_key: str, base_url: str, model: str, dimensions: int,
        batch_size: int = 10, client=None,
    ) -> None:
        if not api_key:
            raise EmbeddingError("缺少百炼 API Key")
        self.model = model
        self.dimensions = dimensions
        self.batch_size = min(batch_size, 10)
        self.client = client or AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30, max_retries=2)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingError("Embedding 输入不能为空")
        result: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                response = await self.client.embeddings.create(
                    model=self.model, input=batch, dimensions=self.dimensions, encoding_format="float"
                )
            except Exception as exc:
                raise EmbeddingError("百炼向量服务暂时不可用") from exc
            ordered = sorted(response.data, key=lambda item: item.index)
            if len(ordered) != len(batch):
                raise EmbeddingError("百炼向量响应数量不一致")
            vectors = [list(item.embedding) for item in ordered]
            if any(len(vector) != self.dimensions for vector in vectors):
                raise EmbeddingError("百炼向量响应维度不一致")
            result.extend(vectors)
        return result

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]
