from types import SimpleNamespace

import pytest

from app.knowledge.embeddings import BailianEmbeddingGateway, EmbeddingError


class FakeEmbeddings:
    def __init__(self, dimensions: int = 3) -> None:
        self.calls = []
        self.dimensions = dimensions

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        values = [SimpleNamespace(index=i, embedding=[float(i + 1)] * self.dimensions) for i, _ in enumerate(kwargs["input"])]
        return SimpleNamespace(data=list(reversed(values)))


class FakeClient:
    def __init__(self, dimensions: int = 3) -> None:
        self.embeddings = FakeEmbeddings(dimensions)


@pytest.mark.anyio
async def test_embedding_gateway_batches_and_restores_response_order() -> None:
    client = FakeClient()
    gateway = BailianEmbeddingGateway(
        api_key="secret", base_url="https://example.com/v1", model="text-embedding-v4",
        dimensions=3, batch_size=2, client=client,
    )
    result = await gateway.embed_documents(["a", "b", "c"])
    assert len(client.embeddings.calls) == 2
    assert result == [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0], [1.0, 1.0, 1.0]]
    assert client.embeddings.calls[0]["dimensions"] == 3
    assert client.embeddings.calls[0]["encoding_format"] == "float"


@pytest.mark.anyio
async def test_embedding_dimension_mismatch_fails_closed() -> None:
    gateway = BailianEmbeddingGateway(
        api_key="secret", base_url="https://example.com/v1", model="text-embedding-v4",
        dimensions=4, batch_size=10, client=FakeClient(dimensions=3),
    )
    with pytest.raises(EmbeddingError, match="维度"):
        await gateway.embed_query("query")


def test_embedding_gateway_requires_key() -> None:
    with pytest.raises(EmbeddingError, match="API Key"):
        BailianEmbeddingGateway(api_key="", base_url="https://example.com", model="m", dimensions=3)
