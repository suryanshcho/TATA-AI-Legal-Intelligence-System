"""
=============================================================================
HUMAN REVIEW AND APPROVAL LAYER
Tata Group AI Legal Document Intelligence System — Standalone Module
=============================================================================
Full-fledged review workflow with:
  - Multi-stage approval chains (reviewer → senior counsel → general counsel)
  - Risk disposition tracking (accept / reject / escalate / defer / mitigate)
  - Summary versioning with diff tracking
  - Reviewer assignment with workload balancing
  - SLA tracking and escalation deadlines
  - Delegation and transfer of review authority
  - Audit trail for every review action
  - Bulk review operations
  - Sample data for demonstration

This module is SEPARATE from the main project and does not modify any
existing project files. It can be run standalone or integrated independently.

Usage:
    python standalone_modules/human_review_approval.py
=============================================================================
"""

import sqlite3
import json
import hashlib
import hmac
import time
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DB_PATH = os.path.join(os.path.dirname(__file__), "review_approval.db")
PEPPER = "tata-legal-review"
SECRET_KEY = "tata-legal-review-secret-2026"
TOKEN_TTL_HOURS = 24

# SLA Deadlines (in hours) per severity
SLA_DEADLINES = {
    "Critical": 4,     # 4 hours
    "High": 24,        # 1 day
    "Medium": 72,      # 3 days
    "Low": 168,        # 7 days
}

# Escalation chain per severity
ESCALATION_CHAIN = {
    "Critical": ["reviewer", "senior_counsel", "general_counsel"],
    "High": ["reviewer", "senior_counsel"],
    "Medium": ["reviewer"],
    "Low": ["reviewer"],
}


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class ReviewAction(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    DEFER = "defer"
    MITIGATE = "mitigate"
    COMMENT = "comment"
    EDIT = "edit"
    REASSIGN = "reassign"
    DELEGATE = "delegate"


class RiskDisposition(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    DEFERRED = "deferred"
    MITIGATED = "mitigated"
    OPEN = "open"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EDITED = "edited"
    DEFERRED = "deferred"


class ReviewerRole(Enum):
    REVIEWER = "reviewer"
    SENIOR_COUNSEL = "senior_counsel"
    GENERAL_COUNSEL = "general_counsel"
    ADMIN = "admin"


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'reviewer',
    password_hash TEXT NOT NULL,
    business_unit TEXT DEFAULT 'Corporate',
    max_concurrent_reviews INTEGER DEFAULT 5,
    active_reviews INTEGER DEFAULT 0,
    is_available INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS review_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name TEXT NOT NULL,
    doc_type TEXT DEFAULT 'Contract',
    business_unit TEXT DEFAULT 'Corporate',
    counterparty TEXT,
    jurisdiction TEXT,
    confidentiality TEXT DEFAULT 'Confidential',
    review_priority TEXT DEFAULT 'Normal',
    status TEXT DEFAULT 'pending_review',
    assigned_reviewer_id INTEGER,
    assigned_at TEXT,
    sla_deadline TEXT,
    escalated_to TEXT,
    escalated_at TEXT,
    owner_email TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(assigned_reviewer_id) REFERENCES review_users(id)
);

CREATE TABLE IF NOT EXISTS review_clauses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    clause_type TEXT NOT NULL,
    label TEXT,
    clause_text TEXT,
    page INTEGER,
    section TEXT,
    confidence REAL DEFAULT 0,
    reviewer_verdict TEXT DEFAULT 'pending',
    reviewer_note TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES review_documents(id)
);

CREATE TABLE IF NOT EXISTS review_risk_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    clause_id INTEGER,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    rationale TEXT,
    evidence TEXT,
    recommendation TEXT,
    confidence REAL DEFAULT 0,
    disposition TEXT DEFAULT 'open',
    reviewer_action TEXT DEFAULT 'pending',
    reviewer_note TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    mitigation_plan TEXT,
    mitigation_deadline TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES review_documents(id)
);

CREATE TABLE IF NOT EXISTS review_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    version INTEGER DEFAULT 1,
    content TEXT,
    obligation_map TEXT,
    missing_clauses TEXT,
    approval_status TEXT DEFAULT 'pending',
    approved_by TEXT,
    approved_at TEXT,
    edit_history TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES review_documents(id)
);

CREATE TABLE IF NOT EXISTS review_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    risk_id INTEGER,
    clause_id INTEGER,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT,
    note TEXT,
    previous_status TEXT,
    new_status TEXT,
    delegation_to TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES review_documents(id)
);

CREATE TABLE IF NOT EXISTS review_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    risk_id INTEGER,
    actor TEXT,
    action TEXT NOT NULL,
    entity TEXT,
    detail TEXT,
    severity TEXT DEFAULT 'info',
    ip_address TEXT,
    session_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS review_sla_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT,
    deadline TEXT,
    triggered_at TEXT,
    acknowledged_at TEXT,
    resolved_at TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(document_id) REFERENCES review_documents(id)
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        conn.execute("BEGIN")
    except sqlite3.OperationalError:
        pass
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


def now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    return hashlib.sha256(f"{PEPPER}:{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def make_token(user_id: int, email: str, role: str) -> str:
    payload = f"{user_id}:{email}:{role}:{int(time.time()) + TOKEN_TTL_HOURS * 3600}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_token(token: str):
    try:
        body, sig = token.rsplit(".", 1)
        expect = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        user_id, email, role, exp = body.split(":")
        if int(exp) < int(time.time()):
            return None
        return {"user_id": int(user_id), "email": email, "role": role}
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# REVIEW WORKFLOW ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class ReviewWorkflowEngine:
    """
    Core engine for the human review and approval workflow.

    Manages:
      - Document assignment to reviewers
      - Risk flag disposition (accept/reject/escalate/defer/mitigate)
      - Summary approval with versioning
      - SLA tracking and automatic escalation
      - Delegation of review authority
      - Bulk review operations
      - Complete audit trail
    """

    def __init__(self):
        init_db()

    # ─── USER MANAGEMENT ───────────────────────────────────────────────

    def create_reviewer(self, email: str, name: str, role: str = "reviewer",
                        password: str = "tata123", business_unit: str = "Corporate",
                        max_concurrent: int = 5) -> dict:
        """Register a new reviewer in the system."""
        with db() as conn:
            conn.execute(
                "INSERT INTO review_users (email, name, role, password_hash, business_unit, max_concurrent_reviews) "
                "VALUES (?,?,?,?,?,?)",
                (email, name, role, hash_password(password), business_unit, max_concurrent))
            user = conn.execute("SELECT * FROM review_users WHERE email=?", (email,)).fetchone()
            self._audit_log(conn, actor=email, action="reviewer_created",
                            entity="user", detail=f"Role: {role}, BU: {business_unit}")
            return dict(user)

    def login(self, email: str, password: str) -> dict:
        """Authenticate reviewer and return token."""
        with db() as conn:
            row = conn.execute("SELECT * FROM review_users WHERE email=?", (email,)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                self._audit_log(conn, actor=email, action="login_failed", entity="auth")
                raise ValueError("Invalid credentials")
            token = make_token(row["id"], row["email"], row["role"])
            self._audit_log(conn, actor=email, action="login", entity="auth")
            return {"token": token, "user": {"id": row["id"], "email": row["email"],
                                             "name": row["name"], "role": row["role"]}}

    def get_available_reviewers(self, role: str = None) -> list:
        """Get reviewers with capacity, optionally filtered by role."""
        with db() as conn:
            q = "SELECT * FROM review_users WHERE is_available=1 AND active_reviews < max_concurrent_reviews"
            params = []
            if role:
                q += " AND role=?"
                params.append(role)
            q += " ORDER BY active_reviews ASC"
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    # ─── DOCUMENT MANAGEMENT ──────────────────────────────────────────

    def submit_document(self, original_name: str, doc_type: str = "Contract",
                        business_unit: str = "Corporate", counterparty: str = "",
                        jurisdiction: str = "", confidentiality: str = "Confidential",
                        review_priority: str = "Normal", owner_email: str = "") -> dict:
        """Submit a document for human review."""
        sla_hours = SLA_DEADLINES.get(review_priority, 72)
        sla_deadline = (datetime.utcnow() + timedelta(hours=sla_hours)).strftime("%Y-%m-%d %H:%M:%S")
        with db() as conn:
            conn.execute(
                "INSERT INTO review_documents "
                "(original_name, doc_type, business_unit, counterparty, jurisdiction, "
                "confidentiality, review_priority, sla_deadline, owner_email) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (original_name, doc_type, business_unit, counterparty, jurisdiction,
                 confidentiality, review_priority, sla_deadline, owner_email))
            doc = conn.execute("SELECT * FROM review_documents ORDER BY id DESC LIMIT 1").fetchone()
            self._audit_log(conn, actor=owner_email or "system", action="document_submitted",
                            entity="document", document_id=doc["id"],
                            detail=f"Priority: {review_priority}, SLA: {sla_deadline}")
            return dict(doc)

    def assign_reviewer(self, document_id: int, reviewer_email: str) -> dict:
        """Assign a document to a specific reviewer."""
        with db() as conn:
            reviewer = conn.execute("SELECT * FROM review_users WHERE email=?",
                                    (reviewer_email,)).fetchone()
            if not reviewer:
                raise ValueError(f"Reviewer {reviewer_email} not found")
            if reviewer["active_reviews"] >= reviewer["max_concurrent_reviews"]:
                raise ValueError(f"Reviewer {reviewer_email} is at capacity")

            conn.execute(
                "UPDATE review_documents SET assigned_reviewer_id=?, assigned_at=?, "
                "status='under_review', updated_at=? WHERE id=?",
                (reviewer["id"], now_str(), now_str(), document_id))
            conn.execute(
                "UPDATE review_users SET active_reviews=active_reviews+1 WHERE id=?",
                (reviewer["id"],))
            self._audit_log(conn, actor="system", action="reviewer_assigned",
                            entity="document", document_id=document_id,
                            detail=f"Assigned to {reviewer_email}")
            doc = conn.execute("SELECT * FROM review_documents WHERE id=?",
                               (document_id,)).fetchone()
            return dict(doc)

    def auto_assign(self, document_id: int) -> dict:
        """Auto-assign to the least-loaded available reviewer."""
        reviewers = self.get_available_reviewers()
        if not reviewers:
            raise ValueError("No available reviewers")
        best = reviewers[0]
        return self.assign_reviewer(document_id, best["email"])

    def get_my_reviews(self, reviewer_email: str) -> list:
        """Get all documents assigned to a reviewer."""
        with db() as conn:
            rows = conn.execute(
                "SELECT d.*, u.name as reviewer_name FROM review_documents d "
                "LEFT JOIN review_users u ON d.assigned_reviewer_id = u.id "
                "WHERE d.assigned_reviewer_id = (SELECT id FROM review_users WHERE email=?) "
                "ORDER BY d.review_priority DESC, d.sla_deadline ASC",
                (reviewer_email,)).fetchall()
            return [dict(r) for r in rows]

    def get_pending_documents(self) -> list:
        """Get all documents awaiting review."""
        with db() as conn:
            rows = conn.execute(
                "SELECT d.*, u.name as reviewer_name FROM review_documents d "
                "LEFT JOIN review_users u ON d.assigned_reviewer_id = u.id "
                "WHERE d.status IN ('pending_review', 'under_review', 'escalated') "
                "ORDER BY d.sla_deadline ASC").fetchall()
            return [dict(r) for r in rows]

    # ─── CLAUSE REVIEW ────────────────────────────────────────────────

    def add_clauses(self, document_id: int, clauses: list) -> list:
        """Add extracted clauses to a document for review."""
        with db() as conn:
            ids = []
            for c in clauses:
                conn.execute(
                    "INSERT INTO review_clauses "
                    "(document_id, clause_type, label, clause_text, page, section, confidence) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (document_id, c["clause_type"], c.get("label", ""),
                     c.get("clause_text", ""), c.get("page"), c.get("section", ""),
                     c.get("confidence", 0)))
                row = conn.execute("SELECT last_insert_rowid()").fetchone()
                ids.append(row[0])
            return ids

    def review_clause(self, clause_id: int, verdict: str, note: str,
                      reviewer_email: str) -> dict:
        """A reviewer gives a verdict on a single clause."""
        with db() as conn:
            clause = conn.execute("SELECT * FROM review_clauses WHERE id=?",
                                  (clause_id,)).fetchone()
            if not clause:
                raise ValueError("Clause not found")
            conn.execute(
                "UPDATE review_clauses SET reviewer_verdict=?, reviewer_note=?, "
                "reviewed_by=?, reviewed_at=? WHERE id=?",
                (verdict, note, reviewer_email, now_str(), clause_id))
            self._audit_log(conn, actor=reviewer_email, action="clause_reviewed",
                            entity="clause", document_id=clause["document_id"],
                            detail=f"Clause {clause_id} ({clause['clause_type']}): {verdict}")
            return {"clause_id": clause_id, "verdict": verdict, "note": note}

    # ─── RISK DISPOSITION ─────────────────────────────────────────────

    def add_risk_flags(self, document_id: int, risks: list) -> list:
        """Add AI-generated risk flags for human review."""
        with db() as conn:
            ids = []
            for r in risks:
                conn.execute(
                    "INSERT INTO review_risk_flags "
                    "(document_id, clause_id, category, severity, rationale, "
                    "evidence, recommendation, confidence) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (document_id, r.get("clause_id"), r["category"], r["severity"],
                     r.get("rationale", ""), r.get("evidence", ""),
                     r.get("recommendation", ""), r.get("confidence", 0)))
                row = conn.execute("SELECT last_insert_rowid()").fetchone()
                ids.append(row[0])
            return ids

    def disposition_risk(self, risk_id: int, action: str, note: str,
                         reviewer_email: str, mitigation_plan: str = None) -> dict:
        """
        Reviewer takes action on a risk flag.
        Actions: accept, reject, escalate, defer, mitigate
        """
        valid_actions = {"accept", "reject", "escalate", "defer", "mitigate"}
        if action not in valid_actions:
            raise ValueError(f"Invalid action. Must be one of: {valid_actions}")

        with db() as conn:
            risk = conn.execute("SELECT * FROM review_risk_flags WHERE id=?",
                                (risk_id,)).fetchone()
            if not risk:
                raise ValueError("Risk flag not found")

            prev_status = risk["disposition"]
            new_status = action if action != "accept" else "accepted"

            # Map action to disposition
            disposition_map = {
                "accept": "accepted", "reject": "rejected", "escalate": "escalated",
                "defer": "deferred", "mitigate": "mitigated"
            }
            new_disposition = disposition_map[action]

            conn.execute(
                "UPDATE review_risk_flags SET disposition=?, reviewer_action=?, "
                "reviewer_note=?, reviewed_by=?, reviewed_at=?, "
                "mitigation_plan=?, mitigation_deadline=? WHERE id=?",
                (new_disposition, action, note, reviewer_email, now_str(),
                 mitigation_plan,
                 (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                 if action == "mitigate" else None,
                 risk_id))

            # Log the action
            self._audit_log(conn, actor=reviewer_email, action=f"risk_{action}",
                            entity="risk_flag", document_id=risk["document_id"],
                            risk_id=risk_id,
                            detail=f"Risk {risk_id} ({risk['category']}): {prev_status} → {new_disposition}",
                            severity="high" if risk["severity"] in ("High", "Critical") else "info")

            # Record the action
            conn.execute(
                "INSERT INTO review_actions "
                "(document_id, risk_id, actor, action, entity, note, previous_status, new_status) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (risk["document_id"], risk_id, reviewer_email, action,
                 "risk_flag", note, prev_status, new_disposition))

            return {"risk_id": risk_id, "action": action,
                    "disposition": new_disposition, "note": note}

    def get_risk_summary(self, document_id: int) -> dict:
        """Get a summary of all risk dispositions for a document."""
        with db() as conn:
            rows = conn.execute(
                "SELECT disposition, COUNT(*) as count FROM review_risk_flags "
                "WHERE document_id=? GROUP BY disposition", (document_id,)).fetchall()
            summary = {r["disposition"]: r["count"] for r in rows}
            total = sum(summary.values())
            return {"document_id": document_id, "total_risks": total,
                    "dispositions": summary}

    # ─── SUMMARY APPROVAL ─────────────────────────────────────────────

    def add_summary(self, document_id: int, content: str,
                    obligation_map: list = None, missing_clauses: list = None) -> dict:
        """Add an AI-generated summary for review."""
        with db() as conn:
            existing = conn.execute(
                "SELECT MAX(version) as v FROM review_summaries WHERE document_id=?",
                (document_id,)).fetchone()
            version = (existing["v"] or 0) + 1
            conn.execute(
                "INSERT INTO review_summaries "
                "(document_id, version, content, obligation_map, missing_clauses) "
                "VALUES (?,?,?,?,?)",
                (document_id, version, content,
                 json.dumps(obligation_map or []),
                 json.dumps(missing_clauses or [])))
            summary = conn.execute(
                "SELECT * FROM review_summaries WHERE document_id=? ORDER BY version DESC LIMIT 1",
                (document_id,)).fetchone()
            return dict(summary)

    def approve_summary(self, document_id: int, reviewer_email: str) -> dict:
        """Approve the latest summary version."""
        with db() as conn:
            conn.execute(
                "UPDATE review_summaries SET approval_status='approved', "
                "approved_by=?, approved_at=? WHERE document_id=? "
                "AND id=(SELECT id FROM review_summaries WHERE document_id=? "
                "ORDER BY version DESC LIMIT 1)",
                (reviewer_email, now_str(), document_id, document_id))
            conn.execute(
                "UPDATE review_documents SET status='approved', updated_at=? WHERE id=?",
                (now_str(), document_id))
            self._audit_log(conn, actor=reviewer_email, action="summary_approved",
                            entity="summary", document_id=document_id)
            return {"document_id": document_id, "status": "approved"}

    def reject_summary(self, document_id: int, reviewer_email: str,
                       reason: str = "") -> dict:
        """Reject the summary — sends back for re-analysis."""
        with db() as conn:
            conn.execute(
                "UPDATE review_summaries SET approval_status='rejected' "
                "WHERE document_id=? AND id=(SELECT id FROM review_summaries "
                "WHERE document_id=? ORDER BY version DESC LIMIT 1)",
                (document_id, document_id))
            conn.execute(
                "UPDATE review_documents SET status='rejected', updated_at=? WHERE id=?",
                (now_str(), document_id))
            self._audit_log(conn, actor=reviewer_email, action="summary_rejected",
                            entity="summary", document_id=document_id,
                            detail=f"Reason: {reason}")
            return {"document_id": document_id, "status": "rejected"}

    def edit_summary(self, document_id: int, new_content: str,
                     editor_email: str) -> dict:
        """Edit the summary (creates a new version)."""
        with db() as conn:
            current = conn.execute(
                "SELECT * FROM review_summaries WHERE document_id=? "
                "ORDER BY version DESC LIMIT 1", (document_id,)).fetchone()
            if not current:
                raise ValueError("No summary found")

            # Store edit in history
            history = json.loads(current["edit_history"] or "[]")
            history.append({
                "version": current["version"],
                "editor": editor_email,
                "edited_at": now_str(),
                "old_content_preview": current["content"][:200] + "..." if current["content"] else "",
            })

            new_version = current["version"] + 1
            conn.execute(
                "INSERT INTO review_summaries "
                "(document_id, version, content, obligation_map, missing_clauses, "
                "approval_status, edit_history) VALUES (?,?,?,?,?,?,?)",
                (document_id, new_version, new_content,
                 current["obligation_map"], current["missing_clauses"],
                 "edited", json.dumps(history)))
            conn.execute(
                "UPDATE review_documents SET status='edited', updated_at=? WHERE id=?",
                (now_str(), document_id))
            self._audit_log(conn, actor=editor_email, action="summary_edited",
                            entity="summary", document_id=document_id,
                            detail=f"Version {current['version']} → {new_version}")
            return {"document_id": document_id, "new_version": new_version}

    def get_summary_versions(self, document_id: int) -> list:
        """Get all versions of a summary with edit history."""
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM review_summaries WHERE document_id=? ORDER BY version ASC",
                (document_id,)).fetchall()
            return [dict(r) for r in rows]

    # ─── ESCALATION ───────────────────────────────────────────────────

    def escalate_document(self, document_id: int, from_email: str,
                          to_role: str = None, reason: str = "") -> dict:
        """Escalate a document to the next level in the chain."""
        with db() as conn:
            doc = conn.execute("SELECT * FROM review_documents WHERE id=?",
                               (document_id,)).fetchone()
            if not doc:
                raise ValueError("Document not found")

            current_reviewer = None
            if doc["assigned_reviewer_id"]:
                current_reviewer = conn.execute(
                    "SELECT * FROM review_users WHERE id=?",
                    (doc["assigned_reviewer_id"],)).fetchone()

            # Determine escalation target
            chain = ESCALATION_CHAIN.get(doc["review_priority"], ["reviewer", "senior_counsel"])
            current_role = current_reviewer["role"] if current_reviewer else "reviewer"
            try:
                idx = chain.index(current_role)
                next_role = chain[idx + 1] if idx + 1 < len(chain) else chain[-1]
            except ValueError:
                next_role = "senior_counsel"

            if to_role:
                next_role = to_role

            # Find available reviewer with the target role
            target = conn.execute(
                "SELECT * FROM review_users WHERE role=? AND is_available=1 "
                "AND active_reviews < max_concurrent_reviews LIMIT 1",
                (next_role,)).fetchone()

            conn.execute(
                "UPDATE review_documents SET status='escalated', "
                "escalated_to=?, escalated_at=?, updated_at=? WHERE id=?",
                (next_role, now_str(), now_str(), document_id))

            # Log escalation
            self._audit_log(conn, actor=from_email, action="document_escalated",
                            entity="document", document_id=document_id,
                            detail=f"Escalated to {next_role}: {reason}",
                            severity="high")

            conn.execute(
                "INSERT INTO review_actions "
                "(document_id, actor, action, entity, note, previous_status, new_status) "
                "VALUES (?,?,?,?,?,?,?)",
                (document_id, from_email, "escalate", "document",
                 reason, doc["status"], "escalated"))

            return {"document_id": document_id, "escalated_to": next_role,
                    "reason": reason}

    # ─── DELEGATION ───────────────────────────────────────────────────

    def delegate_review(self, document_id: int, from_email: str,
                        to_email: str, reason: str = "") -> dict:
        """Delegate review responsibility to another reviewer."""
        with db() as conn:
            doc = conn.execute("SELECT * FROM review_documents WHERE id=?",
                               (document_id,)).fetchone()
            if not doc:
                raise ValueError("Document not found")

            target = conn.execute("SELECT * FROM review_users WHERE email=?",
                                  (to_email,)).fetchone()
            if not target:
                raise ValueError(f"Reviewer {to_email} not found")

            # Update document assignment
            conn.execute(
                "UPDATE review_documents SET assigned_reviewer_id=?, "
                "assigned_at=?, updated_at=? WHERE id=?",
                (target["id"], now_str(), now_str(), document_id))

            # Update reviewer counts
            conn.execute(
                "UPDATE review_users SET active_reviews = active_reviews - 1 WHERE email=?",
                (from_email,))
            conn.execute(
                "UPDATE review_users SET active_reviews = active_reviews + 1 WHERE email=?",
                (to_email,))

            self._audit_log(conn, actor=from_email, action="review_delegated",
                            entity="document", document_id=document_id,
                            detail=f"Delegated from {from_email} to {to_email}: {reason}")

            return {"document_id": document_id, "delegated_to": to_email}

    # ─── SLA MONITORING ───────────────────────────────────────────────

    def check_sla_violations(self) -> list:
        """Check for documents approaching or past their SLA deadline."""
        with db() as conn:
            now = now_str()
            # Past deadline
            overdue = conn.execute(
                "SELECT d.*, u.name as reviewer_name, u.email as reviewer_email "
                "FROM review_documents d LEFT JOIN review_users u "
                "ON d.assigned_reviewer_id = u.id "
                "WHERE d.sla_deadline < ? AND d.status NOT IN ('approved', 'completed', 'rejected')",
                (now,)).fetchall()
            # Approaching (within 25% of remaining time)
            approaching = conn.execute(
                "SELECT d.*, u.name as reviewer_name FROM review_documents d "
                "LEFT JOIN review_users u ON d.assigned_reviewer_id = u.id "
                "WHERE d.sla_deadline > ? AND d.status NOT IN ('approved', 'completed', 'rejected') "
                "AND julianday(d.sla_deadline) - julianday(?) < "
                "0.25 * (julianday(d.sla_deadline) - julianday(d.assigned_at))",
                (now, now)).fetchall()

            results = []
            for r in overdue:
                d = dict(r)
                d["sla_status"] = "overdue"
                hours_over = (datetime.utcnow() - datetime.strptime(d["sla_deadline"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
                d["hours_overdue"] = round(hours_over, 1)
                results.append(d)
            for r in approaching:
                d = dict(r)
                d["sla_status"] = "approaching"
                results.append(d)
            return results

    def trigger_auto_escalation(self) -> list:
        """Auto-escalate overdue documents."""
        violations = self.check_sla_violations()
        escalated = []
        for v in violations:
            if v["sla_status"] == "overdue" and v.get("reviewer_email"):
                try:
                    self.escalate_document(
                        v["id"], from_email="sla_monitor",
                        reason=f"Auto-escalation: SLA overdue by {v.get('hours_overdue', '?')}h")
                    escalated.append(v["id"])
                except ValueError:
                    pass
        return escalated

    # ─── BULK OPERATIONS ──────────────────────────────────────────────

    def bulk_disposition(self, risk_ids: list, action: str, note: str,
                         reviewer_email: str) -> list:
        """Apply the same disposition to multiple risk flags."""
        results = []
        for rid in risk_ids:
            try:
                result = self.disposition_risk(rid, action, note, reviewer_email)
                results.append(result)
            except ValueError as e:
                results.append({"risk_id": rid, "error": str(e)})
        return results

    def bulk_approve(self, document_ids: list, reviewer_email: str) -> list:
        """Approve multiple documents at once."""
        results = []
        for did in document_ids:
            try:
                result = self.approve_summary(did, reviewer_email)
                results.append(result)
            except ValueError as e:
                results.append({"document_id": did, "error": str(e)})
        return results

    # ─── REPORTING ────────────────────────────────────────────────────

    def get_reviewer_stats(self, reviewer_email: str) -> dict:
        """Get performance stats for a reviewer."""
        with db() as conn:
            user = conn.execute("SELECT * FROM review_users WHERE email=?",
                                (reviewer_email,)).fetchone()
            if not user:
                return {}

            approved = conn.execute(
                "SELECT COUNT(*) c FROM review_actions WHERE actor=? AND action='approve'",
                (reviewer_email,)).fetchone()["c"]
            rejected = conn.execute(
                "SELECT COUNT(*) c FROM review_actions WHERE actor=? AND action='reject'",
                (reviewer_email,)).fetchone()["c"]
            escalated = conn.execute(
                "SELECT COUNT(*) c FROM review_actions WHERE actor=? AND action='escalate'",
                (reviewer_email,)).fetchone()["c"]
            total_actions = conn.execute(
                "SELECT COUNT(*) c FROM review_actions WHERE actor=?",
                (reviewer_email,)).fetchone()["c"]

            return {
                "reviewer": reviewer_email,
                "name": user["name"],
                "role": user["role"],
                "active_reviews": user["active_reviews"],
                "max_concurrent": user["max_concurrent_reviews"],
                "total_actions": total_actions,
                "approved": approved,
                "rejected": rejected,
                "escalated": escalated,
                "approval_rate": round(approved / max(total_actions, 1) * 100, 1),
            }

    def get_document_review_trail(self, document_id: int) -> list:
        """Get the complete review trail for a document."""
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM review_actions WHERE document_id=? ORDER BY created_at ASC",
                (document_id,)).fetchall()
            return [dict(r) for r in rows]

    # ─── INTERNAL HELPERS ─────────────────────────────────────────────

    def _audit_log(self, conn, actor, action, entity=None, document_id=None,
                   risk_id=None, detail=None, severity="info"):
        """Write an audit log entry."""
        conn.execute(
            "INSERT INTO review_audit_logs "
            "(document_id, risk_id, actor, action, entity, detail, severity) "
            "VALUES (?,?,?,?,?,?,?)",
            (document_id, risk_id, actor, action, entity, detail, severity))


# ═══════════════════════════════════════════════════════════════════════════
# SAMPLE DATA
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE_CLAUSES = [
    {"clause_type": "indemnity", "label": "Indemnification",
     "clause_text": "Each Party shall indemnify, defend and hold harmless the other Party from and against any third-party claims arising out of negligence or willful misconduct. Indemnification shall not apply to claims arising from the negligence of the indemnified Party.",
     "page": 3, "section": "7. INDEMNITY", "confidence": 0.92},
    {"clause_type": "limitation_of_liability", "label": "Limitation of Liability",
     "clause_text": "Neither Party shall be liable for indirect, incidental, special or consequential damages. Each Party's aggregate liability shall not exceed the total fees paid during the twelve (12) months preceding the claim.",
     "page": 4, "section": "8. LIABILITY", "confidence": 0.88},
    {"clause_type": "confidentiality", "label": "Confidentiality / NDA",
     "clause_text": "Each Party shall keep confidential all non-public information disclosed. Confidentiality obligations survive termination for five (5) years, and indefinitely for trade secrets.",
     "page": 5, "section": "9. CONFIDENTIALITY", "confidence": 0.95},
    {"clause_type": "termination", "label": "Termination",
     "clause_text": "Either Party may terminate for convenience upon thirty (30) days prior written notice. Upon termination, fees for unperformed services shall be refunded pro-rata.",
     "page": 6, "section": "10. TERMINATION", "confidence": 0.90},
    {"clause_type": "data_protection", "label": "Data Protection / Privacy",
     "clause_text": "Personal data processing shall comply with DPDP Act 2023. Cross-border transfers require lawful basis and standard contractual clauses. Breach notification within 72 hours.",
     "page": 7, "section": "11. DATA PROTECTION", "confidence": 0.85},
    {"clause_type": "governing_law", "label": "Governing Law",
     "clause_text": "This Agreement shall be governed by the laws of India. The courts of Mumbai shall have exclusive jurisdiction.",
     "page": 8, "section": "12. GOVERNING LAW", "confidence": 0.97},
    {"clause_type": "payment", "label": "Payment Terms",
     "clause_text": "Invoices shall be paid within thirty (30) days of receipt. Late payments accrue interest at 1.5% per month.",
     "page": 2, "section": "4. PAYMENT", "confidence": 0.91},
    {"clause_type": "warranty", "label": "Warranties",
     "clause_text": "Provider warrants that services shall be performed in a professional and workmanlike manner consistent with industry standards.",
     "page": 5, "section": "6. WARRANTIES", "confidence": 0.87},
]

SAMPLE_RISKS = [
    {"clause_type": "limitation_of_liability", "category": "Unlimited Liability Exposure",
     "severity": "Critical",
     "rationale": "Liability cap tied to 12-month fees may be insufficient for data breach or IP infringement claims that could exceed contract value.",
     "evidence": "aggregate liability shall not exceed the total fees paid during the twelve (12) months",
     "recommendation": "Negotiate carve-outs for data breach, IP indemnification, and confidentiality breach with higher caps.",
     "confidence": 0.94},
    {"clause_type": "termination", "category": "Termination Without Cause",
     "severity": "High",
     "rationale": "Unilateral termination for convenience with only 30-day notice may leave the Company without adequate transition time for critical services.",
     "evidence": "terminate for convenience upon thirty (30) days prior written notice",
     "recommendation": "Extend notice period to 60-90 days for critical services and require transition assistance provisions.",
     "confidence": 0.88},
    {"clause_type": "confidentiality", "category": "Weak Data Protection",
     "severity": "High",
     "rationale": "Confidentiality period of 5 years may be insufficient for trade secrets and sensitive commercial information.",
     "evidence": "Confidentiality obligations survive termination for five (5) years",
     "recommendation": "Extend to 7 years for general confidential information, indefinite for trade secrets. Add specific DPDP Act compliance.",
     "confidence": 0.82},
    {"clause_type": "data_protection", "category": "DPDP Compliance Gap",
     "severity": "Medium",
     "rationale": "While DPDP Act 2023 is referenced, specific data processing addendum and cross-border transfer mechanisms are not detailed.",
     "evidence": "Personal data processing shall comply with DPDP Act 2023",
     "recommendation": "Attach a Data Processing Addendum with specific technical and organizational measures.",
     "confidence": 0.79},
    {"clause_type": "payment", "category": "Payment Terms Imbalance",
     "severity": "Medium",
     "rationale": "30-day payment term with 1.5% monthly penalty is standard but does not account for invoice dispute resolution mechanism.",
     "evidence": "Invoices shall be paid within thirty (30) days. Late payments accrue interest at 1.5% per month",
     "recommendation": "Add dispute resolution mechanism that tolls payment during good-faith disputes.",
     "confidence": 0.75},
    {"clause_type": "indemnity", "category": "Asymmetric Indemnification",
     "severity": "Low",
     "rationale": "Indemnification exclusion for indemnified Party's negligence is standard but may create gap in multi-party scenarios.",
     "evidence": "Indemnification shall not apply to claims arising from the negligence of the indemnified Party",
     "recommendation": "Clarify allocation of liability in shared-negligence scenarios.",
     "confidence": 0.71},
]


def load_sample_data(engine: ReviewWorkflowEngine):
    """Load all sample data for demonstration."""
    print("\n" + "=" * 60)
    print("  LOADING SAMPLE DATA — Human Review & Approval Layer")
    print("=" * 60)

    # Create users
    print("\n[1/5] Creating reviewers...")
    users = [
        ("admin@tata.com", "Tata Legal Admin", "admin", "Corporate", 10),
        ("priya.sharma@tata.com", "Priya Sharma", "senior_counsel", "Legal", 5),
        ("rajesh.kumar@tata.com", "Rajesh Kumar", "reviewer", "Legal", 5),
        ("anita.desai@tata.com", "Anita Desai", "reviewer", "Compliance", 3),
        ("vikram.patel@tata.com", "Vikram Patel", "general_counsel", "Corporate", 8),
    ]
    for email, name, role, bu, max_c in users:
        try:
            u = engine.create_reviewer(email, name, role, "tata123", bu, max_c)
            print(f"  ✓ {name} ({role}) — {email}")
        except sqlite3.IntegrityError:
            print(f"  · {email} already exists")

    # Create documents
    print("\n[2/5] Creating review documents...")
    docs = [
        ("Master Services Agreement — NovaCloud.pdf", "Master Services Agreement",
         "IT Services", "NovaCloud Inc.", "India", "Confidential", "Critical",
         "admin@tata.com"),
        ("Vendor Agreement — Omega Solutions.pdf", "Vendor Agreement",
         "Procurement", "Omega Solutions Ltd.", "USA", "Confidential", "High",
         "rajesh.kumar@tata.com"),
        ("NDA — TechVentures Corp.docx", "NDA",
         "Legal", "TechVentures Corp.", "India", "Restricted", "Medium",
         "priya.sharma@tata.com"),
        ("Employment Contract — Senior Dev.pdf", "Employment Contract",
         "HR", "Internal", "India", "Internal", "Normal",
         "anita.desai@tata.com"),
        ("Data Processing Agreement — CloudFirst.pdf", "Service Agreement",
         "Data Protection", "CloudFirst Analytics", "EU", "Confidential", "High",
         "admin@tata.com"),
    ]
    doc_ids = []
    for name, dtype, bu, party, jur, conf, prio, owner in docs:
        d = engine.submit_document(name, dtype, bu, party, jur, conf, prio, owner)
        doc_ids.append(d["id"])
        print(f"  ✓ [{d['id']}] {name} — Priority: {prio}")

    # Add clauses to first document
    print("\n[3/5] Adding extracted clauses...")
    clause_ids = engine.add_clauses(doc_ids[0], SAMPLE_CLAUSES)
    print(f"  ✓ {len(clause_ids)} clauses added to document #{doc_ids[0]}")

    # Add risk flags
    print("\n[4/5] Adding AI-generated risk flags...")
    risk_ids = engine.add_risk_flags(doc_ids[0], SAMPLE_RISKS)
    print(f"  ✓ {len(risk_ids)} risk flags added to document #{doc_ids[0]}")

    # Add summary
    print("\n[5/5] Adding AI-generated summary...")
    summary_content = """SYSTEM-GENERATED SUMMARY — PENDING LEGAL REVIEW

Parties: This Master Services Agreement is between Tata Manufacturing Systems Limited ("Company") and NovaCloud Inc. ("Provider").

Term: 24-month initial term with automatic 12-month renewals.

Key Obligations:
- Provider shall deliver cloud infrastructure services per Statement of Work
- Company shall pay invoices within 30 days of receipt
- Both parties maintain confidentiality obligations surviving 5 years post-termination

Risk Assessment:
- CRITICAL: Liability cap of 12-month fees may be insufficient for data breach claims
- HIGH: 30-day termination notice may be inadequate for critical services
- HIGH: Confidentiality period may be insufficient for trade secrets
- MEDIUM: DPDP Act compliance needs detailed Data Processing Addendum
- MEDIUM: Payment dispute resolution mechanism absent

Recommendation: Escalate liability and termination provisions to senior counsel before approval. Request Data Processing Addendum attachment."""
    engine.add_summary(doc_ids[0], summary_content,
                       obligation_map=["Payment within 30 days", "Confidentiality 5 years",
                                       "DPDP compliance", "Service delivery per SOW"],
                       missing_clauses=["Force Majeure", "Insurance requirements",
                                         "Non-solicitation"])
    print(f"  ✓ Summary (v1) added to document #{doc_ids[0]}")

    # Assign reviewers
    print("\n  Assigning reviewers...")
    engine.assign_reviewer(doc_ids[0], "priya.sharma@tata.com")
    engine.assign_reviewer(doc_ids[1], "rajesh.kumar@tata.com")
    engine.auto_assign(doc_ids[2])
    print(f"  ✓ Reviewers assigned to 3 documents")

    # Simulate some review actions
    print("\n  Simulating review actions...")
    engine.review_clause(clause_ids[0], "approve", "Standard indemnification — acceptable", "priya.sharma@tata.com")
    engine.disposition_risk(risk_ids[0], "escalate",
                            "Liability cap issue — needs senior counsel review",
                            "priya.sharma@tata.com")
    engine.disposition_risk(risk_ids[2], "mitigate",
                            "Confidentiality period needs extension",
                            "priya.sharma@tata.com",
                            mitigation_plan="Negotiate 7-year general confidentiality, indefinite for trade secrets")
    engine.review_clause(clause_ids[3], "approve", "Standard termination clause", "priya.sharma@tata.com")
    print(f"  ✓ 4 review actions recorded")

    print("\n" + "=" * 60)
    print("  SAMPLE DATA LOADED SUCCESSFULLY")
    print(f"  Users: {len(users)} | Documents: {len(docs)} | Clauses: {len(SAMPLE_CLAUSES)}")
    print(f"  Risk Flags: {len(SAMPLE_RISKS)} | Summary Versions: 1")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — DEMONSTRATION
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "█" * 60)
    print("█  HUMAN REVIEW AND APPROVAL LAYER — Standalone Module")
    print("█  Tata Group AI Legal Document Intelligence System")
    print("█" * 60)

    # Initialize
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    engine = ReviewWorkflowEngine()

    # Load sample data
    load_sample_data(engine)

    # Demonstrate workflow
    print("\n" + "─" * 60)
    print("  WORKFLOW DEMONSTRATION")
    print("─" * 60)

    # 1. Login
    print("\n[DEMO 1] Reviewer Login")
    auth = engine.login("priya.sharma@tata.com", "tata123")
    print(f"  ✓ Logged in as {auth['user']['name']} ({auth['user']['role']})")
    print(f"  Token: {auth['token'][:40]}...")

    # 2. View pending reviews
    print("\n[DEMO 2] Pending Documents")
    pending = engine.get_pending_documents()
    for p in pending:
        print(f"  [{p['id']}] {p['original_name']} — {p['status']} — SLA: {p['sla_deadline']}")

    # 3. View risk summary
    print("\n[DEMO 3] Risk Summary for Document #1")
    risk_summary = engine.get_risk_summary(1)
    print(f"  Total: {risk_summary['total_risks']} risks")
    for disp, count in risk_summary["dispositions"].items():
        print(f"    {disp}: {count}")

    # 4. Check SLA
    print("\n[DEMO 4] SLA Monitoring")
    violations = engine.check_sla_violations()
    if violations:
        for v in violations:
            print(f"  ⚠ [{v['id']}] {v['original_name']} — {v.get('sla_status', '?')}")
    else:
        print("  ✓ No SLA violations")

    # 5. Reviewer stats
    print("\n[DEMO 5] Reviewer Performance")
    stats = engine.get_reviewer_stats("priya.sharma@tata.com")
    print(f"  Reviewer: {stats['name']}")
    print(f"  Active Reviews: {stats['active_reviews']}/{stats['max_concurrent']}")
    print(f"  Total Actions: {stats['total_actions']}")
    print(f"  Approved: {stats['approved']} | Rejected: {stats['rejected']} | Escalated: {stats['escalated']}")
    print(f"  Approval Rate: {stats['approval_rate']}%")

    # 6. Review trail
    print("\n[DEMO 6] Document #1 Review Trail")
    trail = engine.get_document_review_trail(1)
    for t in trail:
        print(f"  [{t['created_at']}] {t['actor']} — {t['action']} — {(t.get('detail') or '')[:60]}")

    # 7. Summary versions
    print("\n[DEMO 7] Summary Version History")
    versions = engine.get_summary_versions(1)
    for v in versions:
        print(f"  v{v['version']} — Status: {v['approval_status']} — By: {v.get('approved_by', 'N/A')}")

    # 8. Escalate
    print("\n[DEMO 8] Escalation")
    result = engine.escalate_document(1, "priya.sharma@tata.com",
                                       reason="Liability cap issue requires general counsel review")
    print(f"  ✓ Document #1 escalated to {result['escalated_to']}")

    print("\n" + "█" * 60)
    print("█  MODULE COMPLETE — Database saved at: review_approval.db")
    print("█" * 60)


if __name__ == "__main__":
    main()
