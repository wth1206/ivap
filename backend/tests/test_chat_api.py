"""P6 chat API tests using LLM_MOCK=true (no network)."""


def test_chat_persists_mock_answer_and_history(client):
    response = client.post("/api/v1/chat", json={"message": "你好，介绍一下平台"})
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["conversation_id"]
    assert payload["message_id"] > 0
    assert payload["is_mock"] is True
    assert "Mock" in payload["answer"]
    assert payload["tool_calls"] == []
    assert payload["citations"] == []

    conversations = client.get("/api/v1/chat/history").json()
    assert conversations["total"] == 1
    assert conversations["items"][0]["conversation_id"] == payload["conversation_id"]

    history = client.get(
        "/api/v1/chat/history",
        params={"conversation_id": payload["conversation_id"]},
    ).json()
    assert history["total"] == 2
    assert [item["role"] for item in history["items"]] == ["user", "assistant"]

    second = client.post(
        "/api/v1/chat",
        json={
            "message": "继续",
            "conversation_id": payload["conversation_id"],
        },
    )
    assert second.status_code == 200

    history2 = client.get(
        "/api/v1/chat/history",
        params={"conversation_id": payload["conversation_id"]},
    ).json()
    assert history2["total"] == 4


def test_chat_unknown_conversation(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "你好", "conversation_id": "0" * 32},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_chat_rejects_empty_message(client):
    response = client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
