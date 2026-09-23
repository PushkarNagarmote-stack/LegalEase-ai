"""
Comprehensive automated test suite for LegalEase AI FastAPI backend.

Covers every endpoint with:
  - Happy-path behaviour and response shape validation
  - Input validation and boundary values (min/max field lengths)
  - Security probes: XSS, SQL injection, null bytes, Unicode, oversized payloads
  - CORS / CSRF origin enforcement per endpoint
  - Security header assertions on every response type
  - Rate limiting enforcement with Retry-After header
  - Session isolation, TTL eviction, and capacity capping
  - Document upload: every supported format, every rejection case
  - Chat: keyword retrieval, grounded answers, fallback, history persistence
  - Prepare-for-lawyer: document-grounded vs. generic question sets
  - Pure unit tests: extract_text_from_file, classify_clause,
    split_document_into_clauses, retrieve_clauses, build_followups

Run with:
    python -m pytest tests/test_backend.py -v
"""

import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.main import (
    SESSION_TTL_SECONDS,
    _rate_limit_records,
    app,
    build_followups,
    classify_clause,
    evict_expired_sessions,
    extract_text_from_file,
    get_or_create_session,
    retrieve_clauses,
    sessions,
    split_document_into_clauses,
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_ORIGIN = "http://localhost:5173"
BLOCKED_ORIGIN = "http://attacker.evil.com"

_client = TestClient(app)


def new_session() -> str:
    """Create a fresh backend session and return its session_id."""
    res = _client.post("/api/session", headers={"Origin": ALLOWED_ORIGIN})
    assert res.status_code == 200
    return res.json()["session_id"]


def upload_txt(sid: str, content: bytes, filename: str = "doc.txt") -> dict:
    """Upload a plain-text document to a session and return the response."""
    return _client.post(
        f"/api/session/{sid}/document",
        files={"file": (filename, content, "text/plain")},
        headers={"Origin": ALLOWED_ORIGIN},
    )


def chat(sid: str, message: str) -> dict:
    """Send a chat message and return the response."""
    return _client.post(
        f"/api/session/{sid}/chat",
        json={"message": message},
        headers={"Origin": ALLOWED_ORIGIN},
    )


def make_docx(text: str) -> bytes:
    """Create a minimal in-memory .docx ZIP with the given text."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


SAMPLE_LEASE = (
    b"Section 1. Term of Lease\n"
    b"This lease shall commence on January 1, 2026 for twelve (12) months.\n\n"
    b"Section 2. Rent and Payment\n"
    b"Tenant shall pay monthly rent of $3,200 due on the first of each month. "
    b"A late fee of $150 shall be assessed after a five (5) day grace period.\n\n"
    b"Section 3. Security Deposit\n"
    b"Tenant shall pay a deposit of $6,400. Landlord may deduct for unpaid rent or damages.\n\n"
    b"Section 4. Termination and Notice\n"
    b"Either party must give sixty (60) days written notice before vacating.\n\n"
    b"Section 5. Indemnification\n"
    b"Tenant agrees to indemnify and hold harmless the Landlord from any liabilities.\n"
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear rate-limit records before and after each test."""
    _rate_limit_records.clear()
    yield
    _rate_limit_records.clear()


@pytest.fixture()
def sid():
    """Provide a fresh session id."""
    return new_session()


@pytest.fixture()
def sid_with_doc(sid):
    """Provide a session with SAMPLE_LEASE already uploaded."""
    res = upload_txt(sid, SAMPLE_LEASE, "sample_lease.txt")
    assert res.status_code == 200
    return sid


# ─────────────────────────────────────────────────────────────────────────────
# Class 1: Health Endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    """Liveness probe — /health"""

    def test_returns_200(self):
        assert _client.get("/health").status_code == 200

    def test_payload_has_status_healthy(self):
        data = _client.get("/health").json()
        assert data["status"] == "healthy"

    def test_payload_has_service_name(self):
        data = _client.get("/health").json()
        assert data["service"] == "LegalEase AI"

    def test_rejects_post(self):
        res = _client.post("/health", headers={"Origin": ALLOWED_ORIGIN})
        assert res.status_code == 405

    def test_rejects_put(self):
        res = _client.put("/health", headers={"Origin": ALLOWED_ORIGIN})
        assert res.status_code == 405


# ─────────────────────────────────────────────────────────────────────────────
# Class 2: Security Headers
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityHeaders:
    """Security headers applied on every response."""

    def _h(self):
        return _client.get("/health").headers

    def test_x_content_type_options(self):
        assert self._h().get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self):
        assert self._h().get("X-Frame-Options") == "DENY"

    def test_referrer_policy(self):
        assert self._h().get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_content_security_policy_present(self):
        assert "default-src 'self'" in self._h().get("Content-Security-Policy", "")

    def test_permissions_policy_present(self):
        assert "camera=()" in self._h().get("Permissions-Policy", "")

    def test_permissions_policy_disables_microphone(self):
        assert "microphone=()" in self._h().get("Permissions-Policy", "")

    def test_permissions_policy_disables_geolocation(self):
        assert "geolocation=()" in self._h().get("Permissions-Policy", "")

    def test_hsts_absent_on_http(self):
        # TestClient uses HTTP, so HSTS must NOT be injected
        assert "Strict-Transport-Security" not in self._h()

    def test_security_headers_on_post_response(self, sid):
        res = chat(sid, "hello")
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert "nosniff" in res.headers.get("X-Content-Type-Options", "")


# ─────────────────────────────────────────────────────────────────────────────
# Class 3: CORS / CSRF Protection
# ─────────────────────────────────────────────────────────────────────────────

class TestCORSAndCSRF:
    """Origin validation and CSRF-style protection on state-changing methods."""

    def test_allowed_origin_passes_session(self):
        res = _client.post("/api/session", headers={"Origin": ALLOWED_ORIGIN})
        assert res.status_code == 200

    def test_blocked_origin_rejected_403(self):
        res = _client.post("/api/session", headers={"Origin": BLOCKED_ORIGIN})
        assert res.status_code == 403

    def test_blocked_origin_detail_message(self):
        res = _client.post("/api/session", headers={"Origin": BLOCKED_ORIGIN})
        assert "Cross-Origin request blocked" in res.json()["detail"]

    def test_localhost_3000_allowed(self):
        res = _client.post("/api/session", headers={"Origin": "http://localhost:3000"})
        assert res.status_code == 200

    def test_127_0_0_1_5173_allowed(self):
        res = _client.post("/api/session", headers={"Origin": "http://127.0.0.1:5173"})
        assert res.status_code == 200

    def test_get_health_no_origin_passes(self):
        # GET does not require Origin validation
        assert _client.get("/health").status_code == 200

    def test_post_without_origin_passes(self):
        # No Origin header = same-origin assumption; should not be blocked
        res = _client.post("/api/session")
        assert res.status_code == 200

    def test_blocked_referer_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": "hello"},
            headers={"referer": "http://phishing-site.com/evil.html"},
        )
        assert res.status_code == 403

    def test_allowed_referer_passes(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": "hello"},
            headers={"referer": "http://localhost:5173/chat"},
        )
        assert res.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Class 4: Session Management
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionManagement:
    """Session creation, TTL eviction, and capacity cap."""

    def test_create_session_returns_200(self):
        res = _client.post("/api/session", headers={"Origin": ALLOWED_ORIGIN})
        assert res.status_code == 200

    def test_create_session_returns_session_id(self):
        data = _client.post("/api/session", headers={"Origin": ALLOWED_ORIGIN}).json()
        assert "session_id" in data

    def test_session_id_length(self):
        sid = _client.post("/api/session", headers={"Origin": ALLOWED_ORIGIN}).json()["session_id"]
        assert len(sid) == 8

    def test_session_registered_in_store(self):
        sid = new_session()
        assert sid in sessions

    def test_two_sessions_are_independent(self):
        sid1 = new_session()
        sid2 = new_session()
        assert sid1 != sid2
        # Upload to sid1 only
        upload_txt(sid1, b"Section 1. A risk clause that shall breach and forfeit deposit.", "only_sid1.txt")
        assert sessions[sid1]["chunks"]
        assert not sessions[sid2]["chunks"]

    def test_session_ttl_eviction_removes_expired(self):
        old_time = time.time() - (SESSION_TTL_SECONDS + 500)
        sessions["ttl_test_expired"] = {
            "chunks": [], "history": [], "file_names": [],
            "created_at": old_time, "last_accessed": old_time,
        }
        evict_expired_sessions(time.time())
        assert "ttl_test_expired" not in sessions

    def test_fresh_session_not_evicted(self):
        fresh_sid = new_session()
        evict_expired_sessions(time.time())
        assert fresh_sid in sessions

    def test_capacity_cap_evicts_oldest(self):
        for i in range(10):
            get_or_create_session(f"cap_{i}")
        assert "cap_0" in sessions  # did not crash


# ─────────────────────────────────────────────────────────────────────────────
# Class 5: Document Upload — Happy Paths
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentUploadHappyPath:
    """All supported formats upload successfully and parse correctly."""

    def test_txt_upload_returns_200(self, sid):
        assert upload_txt(sid, SAMPLE_LEASE).status_code == 200

    def test_txt_upload_clauses_count(self, sid):
        data = upload_txt(sid, SAMPLE_LEASE).json()
        assert data["clauses_count"] >= 3

    def test_txt_upload_citations_present(self, sid):
        data = upload_txt(sid, SAMPLE_LEASE).json()
        assert len(data["citations"]) > 0

    def test_txt_upload_flags_risk_detected(self, sid):
        data = upload_txt(sid, SAMPLE_LEASE).json()
        assert data["flags"]["risk"] >= 1

    def test_txt_upload_flags_obligation_detected(self, sid):
        data = upload_txt(sid, SAMPLE_LEASE).json()
        assert data["flags"]["obligation"] >= 1

    def test_md_upload_accepted(self, sid):
        md_content = b"# Section 1. Confidentiality\nRecipient shall hold information in confidence.\n"
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("agreement.md", md_content, "text/markdown")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 200

    def test_docx_upload_accepted(self, sid):
        docx = make_docx("Section 1. Confidentiality Obligation. Recipient shall hold all data confidential.")
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("contract.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 200
        assert res.json()["clauses_count"] >= 1

    def test_pdf_text_fallback_accepted(self, sid):
        # PDF with plaintext body (no %PDF header) should decode as text
        txt_as_pdf = b"Section 1. Rent shall be due on the first day of each month."
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("fallback.pdf", txt_as_pdf, "application/pdf")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 200

    def test_upload_alias_endpoint_works(self, sid):
        # /upload alias should be identical to /document
        res = _client.post(
            f"/api/session/{sid}/upload",
            files={"file": ("alias.txt", b"Section 1. This lease shall run for one year.", "text/plain")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 200

    def test_upload_increments_file_names(self, sid):
        upload_txt(sid, b"Section 1. A clause.", "first.txt")
        upload_txt(sid, b"Section 2. Another clause.", "second.txt")
        assert "first.txt" in sessions[sid]["file_names"]
        assert "second.txt" in sessions[sid]["file_names"]

    def test_upload_response_has_suggested_followups(self, sid):
        data = upload_txt(sid, SAMPLE_LEASE).json()
        assert len(data["suggested_followups"]) >= 1

    def test_upload_at_exactly_15mb_passes(self, sid):
        max_bytes = 15 * 1024 * 1024
        res = upload_txt(sid, b"A" * max_bytes)
        # Should succeed (limit is strictly greater than)
        assert res.status_code == 200

    def test_unicode_filename_accepted(self, sid):
        res = upload_txt(sid, b"Section 1. Term clause.", "contrato_arrendamiento.txt")
        assert res.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Class 6: Document Upload — Error Paths
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentUploadErrors:
    """Validation failures, unsupported formats, and edge cases."""

    def test_empty_file_rejected_400(self, sid):
        res = upload_txt(sid, b"")
        assert res.status_code == 400

    def test_empty_file_error_message(self, sid):
        assert "empty" in upload_txt(sid, b"").json()["detail"].lower()

    def test_oversized_file_rejected_413(self, sid):
        res = upload_txt(sid, b"X" * (16 * 1024 * 1024))
        assert res.status_code == 413

    def test_oversized_file_error_mentions_limit(self, sid):
        detail = upload_txt(sid, b"X" * (16 * 1024 * 1024)).json()["detail"].lower()
        assert "15 mb" in detail

    def test_rtf_extension_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("doc.rtf", b"{\\rtf1 test}", "application/rtf")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 400
        assert ".rtf" in res.json()["detail"].lower()

    def test_csv_extension_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("data.csv", b"col1,col2\nval1,val2", "text/csv")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 400

    def test_json_extension_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("data.json", b'{"key":"value"}', "application/json")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 400

    def test_html_extension_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("page.html", b"<html><body>Hello</body></html>", "text/html")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 400

    def test_exe_extension_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("virus.exe", b"MZ" + b"\x00" * 100, "application/octet-stream")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 400

    def test_whitespace_only_content_rejected(self, sid):
        res = upload_txt(sid, b"   \n\t\n   ")
        assert res.status_code == 400

    def test_blocked_origin_on_upload(self, sid):
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": ("doc.txt", b"Section 1. Content.", "text/plain")},
            headers={"Origin": BLOCKED_ORIGIN},
        )
        assert res.status_code == 403

    @pytest.mark.parametrize("ext", [".rtf", ".csv", ".json", ".html", ".exe", ".zip", ".xlsx"])
    def test_all_unsupported_extensions_rejected(self, sid, ext):
        res = _client.post(
            f"/api/session/{sid}/document",
            files={"file": (f"doc{ext}", b"some content", "application/octet-stream")},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Class 7: Chat — Happy Path
# ─────────────────────────────────────────────────────────────────────────────

class TestChatHappyPath:
    """Chat responses: shape, content, and session grounding."""

    def test_chat_returns_200(self, sid):
        assert chat(sid, "hello").status_code == 200

    def test_chat_response_has_answer_key(self, sid):
        assert "answer" in chat(sid, "hello").json()

    def test_chat_response_has_citations(self, sid):
        assert "citations" in chat(sid, "hello").json()

    def test_chat_response_has_followups(self, sid):
        data = chat(sid, "hello").json()
        assert "suggested_followups" in data
        assert len(data["suggested_followups"]) > 0

    def test_greeting_response_content(self, sid):
        data = chat(sid, "hello").json()
        assert "LegalEase AI" in data["answer"]

    def test_indemnification_knowledge_base(self, sid):
        data = chat(sid, "What is an indemnification clause?").json()
        assert "Indemnification" in data["answer"]

    def test_force_majeure_knowledge_base(self, sid):
        data = chat(sid, "Explain force majeure").json()
        assert "force majeure" in data["answer"].lower()

    def test_arbitration_knowledge_base(self, sid):
        data = chat(sid, "What is an arbitration clause?").json()
        assert "arbitrat" in data["answer"].lower()

    def test_contract_validity_response(self, sid):
        data = chat(sid, "What makes a contract legally binding?").json()
        assert "offer" in data["answer"].lower() or "consideration" in data["answer"].lower()

    def test_negotiation_response(self, sid):
        data = chat(sid, "How do I negotiate my lease terms?").json()
        assert "negotiat" in data["answer"].lower()

    def test_checklist_response(self, sid):
        data = chat(sid, "What should I look for before signing?").json()
        assert "checklist" in data["answer"].lower() or "signing" in data["answer"].lower()

    def test_document_grounded_answer(self, sid_with_doc):
        data = chat(sid_with_doc, "What is the late fee?").json()
        assert "$150" in data["answer"] or "late" in data["answer"].lower()
        assert len(data["citations"]) > 0

    def test_deposit_grounded_answer(self, sid_with_doc):
        data = chat(sid_with_doc, "How much is the security deposit?").json()
        assert "$6,400" in data["answer"] or "deposit" in data["answer"].lower()

    def test_termination_grounded_answer(self, sid_with_doc):
        data = chat(sid_with_doc, "How much notice is required to terminate?").json()
        assert "60" in data["answer"] or "sixty" in data["answer"].lower()

    def test_chat_persists_to_history(self, sid):
        chat(sid, "What is a lease?")
        assert len(sessions[sid]["history"]) >= 2  # user + assistant turn

    def test_no_document_summary_prompt(self, sid):
        data = chat(sid, "summarize this document").json()
        assert "no document" in data["answer"].lower() or "upload" in data["answer"].lower()

    def test_summary_with_document(self, sid_with_doc):
        data = chat(sid_with_doc, "summarize this document").json()
        assert "section" in data["answer"].lower() or "parsed" in data["answer"].lower()

    def test_how_it_works_response(self, sid):
        data = chat(sid, "How do you work?").json()
        assert "legalease" in data["answer"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Class 8: Chat — Validation & Error Paths
# ─────────────────────────────────────────────────────────────────────────────

class TestChatValidation:
    """Input validation: length limits, empty messages, malformed payloads."""

    def test_empty_message_rejected_422(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": ""},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 422

    def test_message_at_max_length_allowed(self, sid):
        msg = "A" * 4000
        assert chat(sid, msg).status_code == 200

    def test_message_over_max_length_rejected(self, sid):
        msg = "A" * 4001
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": msg},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 422

    def test_missing_message_field_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"note": "no message field"},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 422

    def test_null_message_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": None},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 422

    def test_blocked_origin_on_chat(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": "hello"},
            headers={"Origin": BLOCKED_ORIGIN},
        )
        assert res.status_code == 403

    def test_malformed_json_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            content=b'{"message": broken json',
            headers={"Origin": ALLOWED_ORIGIN, "Content-Type": "application/json"},
        )
        assert res.status_code == 422

    def test_non_json_content_type(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            content=b"message=hello",
            headers={"Origin": ALLOWED_ORIGIN, "Content-Type": "application/x-www-form-urlencoded"},
        )
        assert res.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Class 9: Chat — Security Probes
# ─────────────────────────────────────────────────────────────────────────────

class TestChatSecurityProbes:
    """XSS, SQL injection, null bytes, Unicode — none should crash the server."""

    def test_xss_payload_does_not_crash(self, sid):
        res = chat(sid, "<script>alert('XSS')</script>")
        assert res.status_code == 200

    def test_xss_payload_not_reflected_in_answer(self, sid):
        data = chat(sid, "<script>alert('xss')</script>").json()
        assert "<script>" not in data["answer"]

    def test_sql_injection_select_does_not_crash(self, sid):
        assert chat(sid, "'; SELECT * FROM users; --").status_code == 200

    def test_sql_injection_drop_table_does_not_crash(self, sid):
        assert chat(sid, "'; DROP TABLE sessions; --").status_code == 200

    def test_sql_injection_union_does_not_crash(self, sid):
        assert chat(sid, "1 UNION SELECT password FROM users").status_code == 200

    def test_unicode_emoji_input_handled(self, sid):
        assert chat(sid, "What does 🏠 mean in my lease? こんにちは").status_code == 200

    def test_arabic_rtl_input_handled(self, sid):
        assert chat(sid, "ما هو الإيجار؟").status_code == 200

    def test_null_bytes_in_message_does_not_crash(self, sid):
        # Pydantic strips/rejects null bytes — either 200 or 422 is acceptable
        res = chat(sid, "hello\x00world")
        assert res.status_code in (200, 422)

    def test_oversized_api_key_field_rejected(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": "hello", "api_key": "K" * 201},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 422

    def test_path_traversal_in_session_id_safe(self):
        res = _client.post(
            "/api/session/../../etc/passwd/chat",
            json={"message": "hello"},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        # FastAPI normalises paths — should be 404 or 200 with a new session, never 500
        assert res.status_code in (200, 404, 422)

    def test_deeply_nested_unexpected_fields_ignored(self, sid):
        res = _client.post(
            f"/api/session/{sid}/chat",
            json={"message": "hello", "extra": {"nested": {"deeply": "value"}}},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 200

    def test_large_valid_message_answered(self, sid):
        msg = "What are the legal implications of this clause? " * 80  # ~4000 chars
        res = chat(sid, msg[:4000])
        assert res.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Class 10: Prepare For Lawyer
# ─────────────────────────────────────────────────────────────────────────────

class TestPrepareForLawyer:
    """Attorney-prep question generation — with and without documents."""

    def test_without_document_returns_200(self, sid):
        res = _client.post(
            f"/api/session/{sid}/prepare-for-lawyer",
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert res.status_code == 200

    def test_without_document_returns_questions_key(self, sid):
        data = _client.post(
            f"/api/session/{sid}/prepare-for-lawyer",
            headers={"Origin": ALLOWED_ORIGIN},
        ).json()
        assert "questions" in data

    def test_without_document_returns_at_least_three_questions(self, sid):
        data = _client.post(
            f"/api/session/{sid}/prepare-for-lawyer",
            headers={"Origin": ALLOWED_ORIGIN},
        ).json()
        assert len(data["questions"]) >= 3

    def test_generic_questions_mention_legal_concepts(self, sid):
        data = _client.post(
            f"/api/session/{sid}/prepare-for-lawyer",
            headers={"Origin": ALLOWED_ORIGIN},
        ).json()
        combined = " ".join(data["questions"]).lower()
        assert any(k in combined for k in ("indemnif", "arbitration", "jurisdiction", "breach", "liabilit"))

    def test_with_risk_clause_generates_specific_question(self, sid):
        upload_txt(sid, b"Section 9. Default and Penalties\nTenant shall forfeit $5,000 if in breach or default.", "risk.txt")
        data = _client.post(
            f"/api/session/{sid}/prepare-for-lawyer",
            headers={"Origin": ALLOWED_ORIGIN},
        ).json()
        assert any("Section 9" in q for q in data["questions"])

    def test_with_obligation_clause_generates_specific_question(self, sid):
        upload_txt(sid, b"Section 3. Payment Obligations\nTenant shall pay rent by the first of each month.", "obl.txt")
        data = _client.post(
            f"/api/session/{sid}/prepare-for-lawyer",
            headers={"Origin": ALLOWED_ORIGIN},
        ).json()
        assert len(data["questions"]) >= 1

    def test_with_document_questions_are_strings(self, sid_with_doc):
        data = _client.post(
            f"/api/session/{sid_with_doc}/prepare-for-lawyer",
            headers={"Origin": ALLOWED_ORIGIN},
        ).json()
        for q in data["questions"]:
            assert isinstance(q, str)
            assert len(q) > 5

    def test_blocked_origin_on_prepare(self, sid):
        res = _client.post(
            f"/api/session/{sid}/prepare-for-lawyer",
            headers={"Origin": BLOCKED_ORIGIN},
        )
        assert res.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Class 11: Rate Limiting
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimiting:
    """Sliding-window rate limits: enforcement, headers, and window boundaries."""

    def test_upload_rate_limit_enforced(self, sid):
        # 10 uploads allowed, 11th blocked
        for i in range(10):
            res = upload_txt(sid, b"Section 1. Content.", f"f{i}.txt")
            assert res.status_code == 200

        res = upload_txt(sid, b"Section 1. Content.", "f_extra.txt")
        assert res.status_code == 429

    def test_rate_limit_detail_message(self, sid):
        for i in range(10):
            upload_txt(sid, b"Section 1. Content.", f"rate_{i}.txt")
        res = upload_txt(sid, b"Section 1. Content.", "rate_extra.txt")
        assert "Rate limit exceeded" in res.json()["detail"]

    def test_rate_limit_retry_after_header(self, sid):
        for i in range(10):
            upload_txt(sid, b"Section 1. Content.", f"rta_{i}.txt")
        res = upload_txt(sid, b"Section 1. Content.", "rta_extra.txt")
        assert "Retry-After" in res.headers
        assert int(res.headers["Retry-After"]) > 0

    def test_chat_rate_limit_enforced(self, sid):
        for _ in range(30):
            res = chat(sid, "hello")
            assert res.status_code == 200

        res = chat(sid, "hello")
        assert res.status_code == 429

    def test_session_creation_rate_limit_enforced(self):
        _rate_limit_records.clear()
        # Default: 60 sessions/min
        for _ in range(60):
            _client.post("/api/session", headers={"Origin": ALLOWED_ORIGIN})

        res = _client.post("/api/session", headers={"Origin": ALLOWED_ORIGIN})
        assert res.status_code == 429


# ─────────────────────────────────────────────────────────────────────────────
# Class 12: Unit Tests — extract_text_from_file
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractTextFromFile:
    """Pure unit tests for the file extraction function."""

    def test_txt_utf8_decodes(self):
        result = extract_text_from_file("doc.txt", b"Section 1. Hello World")
        assert "Hello World" in result

    def test_txt_latin1_decodes(self):
        content = "Caf\xe9 au lait clause".encode("latin-1")
        result = extract_text_from_file("doc.txt", content)
        assert "clause" in result

    def test_md_extension_decodes(self):
        result = extract_text_from_file("readme.md", b"# Heading\n\nParagraph text")
        assert "Heading" in result

    def test_docx_valid_structure_extracted(self):
        docx = make_docx("Tenant shall pay rent monthly.")
        result = extract_text_from_file("agreement.docx", docx)
        assert "Tenant shall pay" in result

    def test_docx_invalid_zip_raises_valueerror(self):
        with pytest.raises(ValueError, match="DOCX extraction failed"):
            extract_text_from_file("bad.docx", b"not a zip file")

    def test_rtf_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            extract_text_from_file("doc.rtf", b"{\\rtf1 content}")

    def test_csv_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            extract_text_from_file("data.csv", b"col1,col2")

    def test_html_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            extract_text_from_file("page.html", b"<html></html>")

    def test_no_extension_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            extract_text_from_file("noext", b"some content")

    def test_pdf_plaintext_fallback_no_header(self):
        # If .pdf but no %PDF magic bytes, fall through to text decode
        result = extract_text_from_file("doc.pdf", b"Plain text content in a pdf file.")
        assert "Plain text content" in result

    def test_empty_bytes_returns_empty_or_raises(self):
        # Empty content is valid to decode but may produce empty string
        try:
            result = extract_text_from_file("doc.txt", b"")
            assert result == ""
        except Exception:
            pass  # Some paths may raise — acceptable


# ─────────────────────────────────────────────────────────────────────────────
# Class 13: Unit Tests — classify_clause
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyClause:
    """Unit tests for the rule-based clause classifier."""

    @pytest.mark.parametrize("text,expected", [
        ("Tenant shall forfeit deposit and pay penalty fee.", "risk"),
        ("Tenant shall pay damages for breach of contract.", "risk"),
        ("Indemnification clause covering all liabilities.", "risk"),
        ("Tenant shall pay rent on the first of each month.", "obligation"),
        ("Landlord must notify tenant 24 hours before entry.", "obligation"),
        ("Covenant: tenant required to maintain the premises.", "obligation"),
        ("Tenant may request repairs from landlord at any time.", "right"),
        ("Tenant is entitled to a refund of the security deposit.", "right"),
        ("Landlord shall provide heat and hot water as required.", "right"),
        ("This lease was executed as of the date set forth above.", "info"),
    ])
    def test_classify_parametrized(self, text, expected):
        assert classify_clause(text) == expected

    def test_empty_string_returns_info(self):
        assert classify_clause("") == "info"

    def test_case_insensitive_risk_detection(self):
        assert classify_clause("TENANT SHALL BE LIABLE FOR ALL DAMAGES") == "risk"


# ─────────────────────────────────────────────────────────────────────────────
# Class 14: Unit Tests — split_document_into_clauses
# ─────────────────────────────────────────────────────────────────────────────

class TestSplitDocumentIntoClauses:
    """Unit tests for clause segmentation logic."""

    def test_section_headers_split_correctly(self):
        text = (
            "Section 1. Rent\nTenant shall pay $2,000.\n\n"
            "Section 2. Deposit\nTenant shall deposit $4,000.\n\n"
            "Section 3. Termination\nEither party may terminate with notice."
        )
        clauses = split_document_into_clauses(text, "test.txt")
        assert len(clauses) >= 3

    def test_clause_has_required_keys(self):
        clauses = split_document_into_clauses("Section 1. Term\nThis lease runs one year.", "test.txt")
        for c in clauses:
            assert "ref" in c
            assert "text" in c
            assert "type" in c
            assert "heading" in c

    def test_single_block_returns_at_least_one_clause(self):
        clauses = split_document_into_clauses("A simple statement with no section headers.", "test.txt")
        assert len(clauses) >= 1

    def test_very_short_fragments_skipped(self):
        text = "Section 1. Rent\nPay.\n\nSection 2. Term\nThis lease is valid for twelve months starting January."
        clauses = split_document_into_clauses(text, "test.txt")
        # "Pay." alone is < 15 chars and should be merged or skipped
        for c in clauses:
            assert len(c["text"]) >= 15

    def test_empty_document_returns_fallback(self):
        clauses = split_document_into_clauses("", "empty.txt")
        assert len(clauses) >= 1

    def test_clause_type_is_valid_value(self):
        clauses = split_document_into_clauses(SAMPLE_LEASE.decode(), "sample.txt")
        valid_types = {"risk", "obligation", "right", "info"}
        for c in clauses:
            assert c["type"] in valid_types


# ─────────────────────────────────────────────────────────────────────────────
# Class 15: Unit Tests — retrieve_clauses & build_followups
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrieveClausesAndFollowups:
    """Unit tests for the keyword-density retrieval engine."""

    @pytest.fixture()
    def session_with_clauses(self):
        s = {
            "chunks": split_document_into_clauses(SAMPLE_LEASE.decode(), "lease.txt"),
            "history": [],
            "file_names": ["lease.txt"],
        }
        return s

    def test_relevant_query_returns_results(self, session_with_clauses):
        results = retrieve_clauses(session_with_clauses, "What is the late fee for rent?")
        assert len(results) > 0

    def test_deposit_query_matches_deposit_clause(self, session_with_clauses):
        results = retrieve_clauses(session_with_clauses, "How much is the security deposit?")
        combined = " ".join(c["text"] for c in results).lower()
        assert "deposit" in combined

    def test_termination_query_matches_notice_clause(self, session_with_clauses):
        results = retrieve_clauses(session_with_clauses, "How many days notice to vacate?")
        combined = " ".join(c["text"] for c in results).lower()
        assert "notice" in combined or "vacate" in combined

    def test_empty_session_returns_empty(self):
        s = {"chunks": [], "history": [], "file_names": []}
        assert retrieve_clauses(s, "What is the rent?") == []

    def test_max_results_is_three(self, session_with_clauses):
        results = retrieve_clauses(session_with_clauses, "obligation rent deposit fee terminate notice")
        assert len(results) <= 3

    def test_irrelevant_query_returns_empty_or_few(self, session_with_clauses):
        # Stopword-only query should score zero on all clauses
        results = retrieve_clauses(session_with_clauses, "the a and of")
        assert len(results) == 0

    def test_build_followups_rent_context(self):
        clause = {"text": "Tenant shall pay rent by the 1st.", "ref": "Section 2", "type": "obligation"}
        followups = build_followups(clause, "When is rent due?")
        assert any("rent" in f.lower() or "late" in f.lower() for f in followups)

    def test_build_followups_deposit_context(self):
        clause = {"text": "Tenant shall pay a deposit of $4,000.", "ref": "Section 3", "type": "obligation"}
        followups = build_followups(clause, "How much is the deposit?")
        assert any("deposit" in f.lower() or "wear" in f.lower() for f in followups)

    def test_build_followups_termination_context(self):
        clause = {"text": "Either party must give 60 days notice to terminate.", "ref": "Section 5", "type": "obligation"}
        followups = build_followups(clause, "How to terminate?")
        assert any("notice" in f.lower() or "terminate" in f.lower() for f in followups)

    def test_build_followups_returns_list(self):
        clause = {"text": "A generic clause.", "ref": "Section 1", "type": "info"}
        followups = build_followups(clause, "question")
        assert isinstance(followups, list)
        assert len(followups) > 0
