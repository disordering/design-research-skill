import asyncio
import base64
import io
import re
import zipfile

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.session_contracts import SessionCreate, SourceInput
from tests.test_session_service import create_service, request


def test_session_routes_and_exports_share_the_same_stored_snapshot(tmp_path):
    service, _ = create_service(tmp_path)
    with TestClient(create_app(session_service_factory=lambda: service)) as client:
        caps = client.get("/api/review-sessions/capabilities")
        assert caps.status_code == 200
        assert caps.json()["rules"] == 24
        assert caps.json()["perception"]["deterministic_metrics"] is True
        response = client.post("/api/review-sessions", json=request().model_dump(mode="json"))
        assert response.status_code == 201, response.text
        session_id = response.json()["session_id"]
        finished = asyncio.run(service.run(session_id))
        snapshot = client.get(f"/api/review-sessions/{session_id}").json()
        assert snapshot["report_version"] == finished.report_version
        report = client.get(f"/api/review-sessions/{session_id}/reports/1")
        assert report.status_code == 200
        export = client.get(f"/api/review-sessions/{session_id}/export")
        assert export.status_code == 200
        assert "text/markdown" in export.headers["content-type"]
        assert "契约测试判断" in export.text
        assert "T01–T10" in export.text and "证据链总表" in export.text
        summary = client.get(f"/api/review-sessions/{session_id}/export", params={"format": "summary"})
        assert summary.status_code == 200 and "评审摘要" in summary.text
        audit = client.get(f"/api/review-sessions/{session_id}/export", params={"format": "audit"})
        assert audit.status_code == 200 and "逐项检查与判断" in audit.text
        structured = client.get(f"/api/review-sessions/{session_id}/structured-report")
        assert structured.status_code == 200
        assert len(structured.json()["process"]) == 10
        assert structured.json()["checks"][0]["evidence_chain"]
        assert "state_graph" in structured.json()
        package = client.get(f"/api/review-sessions/{session_id}/package")
        assert package.status_code == 200
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            names = set(archive.namelist())
            showcase = archive.read("report-showcase.md").decode("utf-8")
        assert {"report-showcase.md", "report-details.md", "report-summary.md", "report.json",
                "process.json", "checks.json", "evidence.json", "findings.json",
                "flow-graph.json", "coverage.json", "contract-violations.json",
                "stages/T01.json", "stages/T10.json", "stages/index.json",
                "method/05-判据库-v0.2.json",
                "method/07-会话变更重查与复审规则.md"} <= names
        local_links = [
            link for link in re.findall(r"\]\(([^)]+)\)", showcase)
            if "://" not in link and not link.startswith(("/api/", "data:"))
        ]
        assert local_links and all(link.split("#", 1)[0] in names for link in local_links)
        unchanged = client.get(f"/api/review-sessions/{session_id}/updates", params={"after_sequence": snapshot["sequence"]}).json()
        assert not unchanged["changed"] and unchanged["snapshot"] is None


def test_invalid_sources_events_and_unknown_sessions_are_stable_errors(tmp_path):
    service, _ = create_service(tmp_path)
    with TestClient(create_app(session_service_factory=lambda: service)) as client:
        assert client.get("/api/review-sessions/missing").status_code == 404
        bad = request().model_dump(mode="json")
        bad["sources"] = [{"kind": "website", "reference": "file:///secret"}]
        assert client.post("/api/review-sessions", json=bad).status_code == 422
        session = service.create(request())
        response = client.post(f"/api/review-sessions/{session.session_id}/events", json={
            "event_id": "bad-source", "expected_context_version": 1, "type": "add_sources",
            "payload": {"sources": [{"kind": "website", "reference": "javascript:run()"}]},
        })
        assert response.status_code == 422
        assert service.store.get(session.session_id).context_version == 1
        response = client.post(f"/api/review-sessions/{session.session_id}/events", json={
            "event_id": "stale", "expected_context_version": 9, "type": "finish",
        })
        assert response.status_code == 409


def test_artifact_api_does_not_accept_foreign_session_or_filesystem_paths(tmp_path):
    service, _ = create_service(tmp_path)
    a, b = service.create(request()), service.create(request())
    artifact = service.store.write_artifact(a.session_id, b"evidence", "text/plain")
    with TestClient(create_app(session_service_factory=lambda: service)) as client:
        assert client.get(f"/api/review-sessions/{a.session_id}/artifacts/{artifact}").text == "evidence"
        assert client.get(f"/api/review-sessions/{b.session_id}/artifacts/{artifact}").status_code == 404


def test_run_endpoint_schedules_an_existing_session(tmp_path, monkeypatch):
    service, _ = create_service(tmp_path)
    session = service.create(request())
    submitted = []
    monkeypatch.setattr(service, "submit", lambda session_id: submitted.append(session_id))
    with TestClient(create_app(session_service_factory=lambda: service)) as client:
        response = client.post(f"/api/review-sessions/{session.session_id}/run")
    assert response.status_code == 202
    assert submitted == [session.session_id]


def test_uploaded_document_and_material_context_are_available_to_frontend(tmp_path):
    from engine.session_adapters import AdapterHub
    from engine.session_service import SessionService
    from engine.session_store import SessionStore
    from tests.test_session_context_pipeline import BusinessFixture, business_request

    service = SessionService(SessionStore(tmp_path), adapters=AdapterHub(), model_factory=lambda _: BusinessFixture())
    data = business_request().model_dump(mode="json")
    data["sources"][0].update(
        filename="brief.md", document_base64=base64.b64encode(data["sources"][0]["content"].encode()).decode(),
        content="",
    )
    with TestClient(create_app(session_service_factory=lambda: service)) as client:
        created = client.post("/api/review-sessions", json=data)
        assert created.status_code == 201, created.text
        assert created.json()["sources"][0]["input"]["document_base64"] == ""
        sid = created.json()["session_id"]
        asyncio.run(service.run(sid))
        snapshot = client.get(f"/api/review-sessions/{sid}").json()
        assert snapshot["material_understanding"]["opinions"][0]["id"] == "OP01"
        assert snapshot["active_phase"] == "T09"
        original = next(e["original_artifact_id"] for e in snapshot["evidence"] if e["original_artifact_id"])
        content = client.get(f"/api/review-sessions/{sid}/artifacts/{original}")
        assert content.status_code == 200 and content.content.decode().startswith("设计目的")
        report = client.get(f"/api/review-sessions/{sid}/export").text
        assert "目标要求对应" in report and "原始文件" in report
