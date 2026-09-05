from fastapi.testclient import TestClient
import pytest

from interview_agent.embeddings.embedding import EmbeddingConfig, EmbeddingServiceClient
from interview_agent.embeddings.embedding_service import EmbeddingServiceSettings, create_app


class FakeLocalEmbeddingClient:
    def __init__(self, config) -> None:
        self.config = config

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


def test_embedding_service_embeds_texts(monkeypatch) -> None:
    import interview_agent.embeddings.embedding_service as service_module

    monkeypatch.setattr(service_module, "LocalEmbeddingClient", FakeLocalEmbeddingClient)
    app = create_app(EmbeddingServiceSettings(model="fake-model"))

    with TestClient(app) as client:
        health = client.get("/health")
        response = client.post("/embed", json={"texts": ["RAG", "AgentLoop"]})

    assert health.json()["model"] == "fake-model"
    assert response.status_code == 200
    assert response.json()["vectors"] == [[3.0, 1.0], [9.0, 1.0]]
    assert response.json()["dimensions"] == 2


def test_embedding_service_client_rejects_mismatched_vector_count(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"vectors": [[1.0, 0.0]]}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("interview_agent.embeddings.embedding.requests.post", fake_post)
    client = EmbeddingServiceClient(EmbeddingConfig(provider="service"))

    with pytest.raises(RuntimeError, match="returned 1 vectors for 2 input texts"):
        client.embed_texts(["one", "two"])
