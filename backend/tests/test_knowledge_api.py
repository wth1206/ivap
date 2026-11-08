"""P5 knowledge base tests with mock embeddings and mock LLM."""

import io

import fitz
from docx import Document


def _upload(client, filename: str, data: bytes):
    return client.post(
        "/api/v1/knowledge/upload",
        files={"file": (filename, data, "application/octet-stream")},
    )


def _txt_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def _pdf_bytes(pages) -> bytes:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def _docx_bytes(paragraphs) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_txt_upload_search_ask_and_delete(client):
    content = (
        "VisDrone 数据集包含 car、pedestrian、people、bicycle、van、truck 等类别。\n"
        "无人机遥感图像的目标检测需要关注小目标和密集场景。\n"
        "ECE-YOLO 使用 ESPMStem 和 DynamicHead 改进检测头。\n"
    )
    uploaded = _upload(client, "visdrone.txt", _txt_bytes(content))
    assert uploaded.status_code == 201, uploaded.text

    document = uploaded.json()
    assert document["status"] == "ready"
    assert document["file_type"] == "txt"
    assert document["page_count"] is None
    assert document["chunk_count"] > 0
    assert document["created_at"].endswith("Z")

    listed = client.get("/api/v1/knowledge/documents")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    search = client.post(
        "/api/v1/knowledge/search",
        json={"query": "VisDrone 数据集包含哪些类别？", "top_k": 3, "score_threshold": 0.0},
    )
    assert search.status_code == 200, search.text
    results = search.json()["results"]
    assert results
    assert results[0]["document_name"] == "visdrone.txt"
    assert results[0]["page_no"] is None
    assert "VisDrone" in results[0]["content"]

    asked = client.post(
        "/api/v1/knowledge/ask",
        json={"query": "VisDrone 数据集包含哪些类别？", "top_k": 3, "score_threshold": 0.0},
    )
    assert asked.status_code == 200, asked.text
    answer = asked.json()
    assert answer["no_answer"] is False
    assert answer["is_mock"] is True
    assert answer["answer"]
    assert len(answer["citations"]) == len(results)

    duplicate = _upload(client, "visdrone-copy.txt", _txt_bytes(content))
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DOCUMENT_DUPLICATED"

    deleted = client.delete(f"/api/v1/knowledge/documents/{document['document_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert deleted.json()["removed_vectors"] > 0

    assert client.get("/api/v1/knowledge/documents").json()["total"] == 0
    empty = client.post(
        "/api/v1/knowledge/search",
        json={"query": "VisDrone", "top_k": 3, "score_threshold": 0.0},
    )
    assert empty.status_code == 200
    assert empty.json()["no_answer"] is True
    assert empty.json()["results"] == []


def test_pdf_preserves_page_numbers(client):
    data = _pdf_bytes(
        [
            "VisDrone dataset page one. It contains cars and pedestrians.",
            "VisDrone dataset page two. Small object detection is difficult.",
        ]
    )
    uploaded = _upload(client, "visdrone.pdf", data)
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["page_count"] == 2
    assert document["chunk_count"] >= 1

    search = client.post(
        "/api/v1/knowledge/search",
        json={"query": "VisDrone dataset", "top_k": 5, "score_threshold": 0.0},
    )
    assert search.status_code == 200
    results = search.json()["results"]
    assert results
    assert results[0]["page_no"] in (1, 2)


def test_docx_paragraph_metadata(client):
    data = _docx_bytes(
        [
            "ECE-YOLO improves the detection head with DynamicHead.",
            "The ESPMStem module preserves spatial details before downsampling.",
        ]
    )
    uploaded = _upload(client, "ece.docx", data)
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["file_type"] == "docx"
    assert document["page_count"] is None

    search = client.post(
        "/api/v1/knowledge/search",
        json={"query": "ESPMStem spatial details", "top_k": 5, "score_threshold": 0.0},
    )
    results = search.json()["results"]
    assert results
    assert results[0]["page_no"] is None
    assert results[0]["extra"] is not None


def test_invalid_document_type(client):
    response = _upload(client, "notes.md", b"# not supported")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"
