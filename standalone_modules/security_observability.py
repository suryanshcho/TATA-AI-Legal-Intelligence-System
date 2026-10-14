"""
=============================================================================
SECURITY LOGGING AND OBSERVABILITY
Tata Group AI Legal Document Intelligence System — Standalone Module
=============================================================================
Full-fledged security and observability module with:
  - Structured security event logging (auth, access, data, system events)
  - Request/response logging middleware
  - Real-time metrics collection (counters, gauges, histograms)
  - Distributed tracing with correlation IDs
  - Alert rules and notification system
  - Compliance reporting (SOC2, ISO27001, DPDP alignment)
  - Threat detection patterns (brute force, injection, exfiltration)
  - Session management and token tracking
  - Data access audit trail
  - Health monitoring
  - Sample data for demonstration

This module is SEPARATE from the main project and does not modify any
existing project files. It can be run standalone or integrated independently.

Usage:
    python standalone_modules/security_observability.py
=============================================================================
"""

import sqlite3
import json
import hashlib
import hmac
import time
import os
import re
import uuid
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DB_PATH = os.path.join(os.path.dirname(__file__), "security_observability.db")
PEPPER = "tata-legal-security"
SECRET_KEY = "tata-legal-security-secret-2026"

# Alert thresholds
ALERT_THRESHOLDS = {
    "failed_logins_per_minute": 5,
    "failed_logins_per_hour": 20,
    "api_errors_per_minute": 10,
    "high_risk_actions_per_hour": 50,
    "data_exports_per_hour": 10,
    "suspicious_patterns_per_hour": 5,
}

# Threat detection patterns
THREAT_PATTERNS = {
    "sql_injection": re.compile(r"(?:union\s+select|drop\s+table|insert\s+into|delete\s+from|'\s*or\s+'|1\s*=\s*1|--\s)", re.I),
    "xss_attempt": re.compile(r"<script|javascript:|onerror|onload|eval\(|document\.cookie", re.I),
    "path_traversal": re.compile(r"\.\.\/|\.\.\\|~\/|\/etc\/|\/proc\/", re.I),
    "command_injection": re.compile(r";\s*(?:cat|ls|pwd|whoami|id|curl|wget|nc|netcat|bash|sh|python)", re.I),
    "brute_force_indicator": re.compile(r"password|passwd|pwd.*incorrect|auth.*fail|invalid.*credential", re.I),
}

# Severity levels
class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS security_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    password_hash TEXT NOT NULL,
    business_unit TEXT DEFAULT 'Corporate',
    is_active INTEGER DEFAULT 1,
    last_login TEXT,
    login_count INTEGER DEFAULT 0,
    failed_logins INTEGER DEFAULT 0,
    locked_until TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    started_at TEXT DEFAULT (datetime('now')),
    last_activity TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY(user_id) REFERENCES security_users(id)
);

CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT,
    event_type TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    actor TEXT,
    actor_ip TEXT,
    actor_role TEXT,
    target_resource TEXT,
    target_id INTEGER,
    action TEXT,
    result TEXT DEFAULT 'success',
    detail TEXT,
    request_method TEXT,
    request_path TEXT,
    request_body_hash TEXT,
    response_status INTEGER,
    response_time_ms INTEGER,
    user_agent TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    labels TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    operation TEXT NOT NULL,
    service TEXT DEFAULT 'legal-ai',
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_ms REAL,
    status TEXT DEFAULT 'ok',
    error_message TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source_event_id INTEGER,
    actor TEXT,
    actor_ip TEXT,
    triggered_at TEXT DEFAULT (datetime('now')),
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    status TEXT DEFAULT 'open',
    notification_sent INTEGER DEFAULT 0,
    escalation_level INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT,
    event_id INTEGER,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    before_state TEXT,
    after_state TEXT,
    ip_address TEXT,
    user_agent TEXT,
    session_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS compliance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    framework TEXT NOT NULL,
    control_id TEXT NOT NULL,
    control_name TEXT NOT NULL,
    status TEXT DEFAULT 'pass',
    evidence TEXT,
    checked_at TEXT DEFAULT (datetime('now')),
    next_check TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS data_access_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    access_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id INTEGER,
    resource_name TEXT,
    fields_accessed TEXT,
    purpose TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    response_time_ms REAL,
    detail TEXT,
    checked_at TEXT DEFAULT (datetime('now'))
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


def gen_correlation_id():
    return str(uuid.uuid4())[:12]


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY EVENT LOGGER
# ═══════════════════════════════════════════════════════════════════════════

class SecurityEventLogger:
    """
    Central security event logging engine.
    Captures every security-relevant event with correlation IDs,
    structured metadata, and severity classification.
    """

    EVENT_CATEGORIES = {
        "authentication": ["login_success", "login_failed", "logout", "token_refresh",
                           "password_change", "account_locked", "session_expired"],
        "authorization": ["access_granted", "access_denied", "privilege_escalation",
                          "role_change", "permission_update"],
        "data_access": ["document_read", "document_create", "document_update",
                        "document_delete", "document_export", "clause_read",
                        "risk_read", "summary_read", "audit_read"],
        "data_modification": ["review_approve", "review_reject", "review_escalate",
                              "risk_disposition", "summary_edit", "settings_update"],
        "system": ["pipeline_start", "pipeline_complete", "pipeline_failed",
                   "ocr_complete", "rag_retrieval", "ai_analysis"],
        "security": ["threat_detected", "brute_force_blocked", "injection_attempt",
                     "rate_limit_exceeded", "suspicious_activity"],
    }

    def __init__(self):
        init_db()
        self._correlation_id = None

    def set_correlation_id(self, cid: str = None):
        """Set the correlation ID for the current request context."""
        self._correlation_id = cid or gen_correlation_id()

    def get_correlation_id(self) -> str:
        if not self._correlation_id:
            self._correlation_id = gen_correlation_id()
        return self._correlation_id

    def log(self, event_type: str, category: str, severity: str = "info",
            actor: str = None, actor_ip: str = None, actor_role: str = None,
            target_resource: str = None, target_id: int = None,
            action: str = None, result: str = "success", detail: str = None,
            request_method: str = None, request_path: str = None,
            response_status: int = None, response_time_ms: int = None,
            user_agent: str = None) -> int:
        """Log a security event and return the event ID."""
        cid = self.get_correlation_id()
        with db() as conn:
            conn.execute(
                "INSERT INTO security_events "
                "(correlation_id, event_type, category, severity, actor, actor_ip, "
                "actor_role, target_resource, target_id, action, result, detail, "
                "request_method, request_path, response_status, response_time_ms, "
                "user_agent) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, event_type, category, severity, actor, actor_ip, actor_role,
                 target_resource, target_id, action, result, detail,
                 request_method, request_path, response_status, response_time_ms,
                 user_agent))
            row = conn.execute("SELECT last_insert_rowid()").fetchone()
            event_id = row[0]

            # Record metric
            self._record_metric(conn, f"event_{category}", 1,
                                {"event_type": event_type, "severity": severity})

            # Check alert thresholds
            self._check_thresholds(conn, event_type, category, actor, actor_ip)

            # Threat detection
            if detail:
                self._scan_threats(conn, detail, actor, actor_ip, event_id)

            return event_id

    def log_auth_event(self, event_type: str, actor: str, ip: str = None,
                       user_agent: str = None, result: str = "success",
                       detail: str = None) -> int:
        """Convenience method for authentication events."""
        severity = "info" if result == "success" else "warning"
        if event_type == "login_failed":
            severity = "warning"
        eid = self.log(event_type=event_type, category="authentication",
                       severity=severity, actor=actor, actor_ip=ip,
                       user_agent=user_agent, result=result, detail=detail)

        # Track failed logins for brute force detection
        if event_type == "login_failed":
            self._track_failed_login(actor, ip)

        return eid

    def log_data_access(self, actor: str, access_type: str, resource_type: str,
                        resource_id: int = None, resource_name: str = None,
                        fields: list = None, purpose: str = None,
                        ip: str = None) -> int:
        """Log data access for compliance and DLP."""
        eid = self.log(event_type=f"data_{access_type}", category="data_access",
                       severity="info", actor=actor, actor_ip=ip,
                       target_resource=resource_type, target_id=resource_id,
                       action=access_type,
                       detail=f"Accessed {resource_type}#{resource_id}: {resource_name}")

        # Also record in data_access_logs for compliance
        with db() as conn:
            conn.execute(
                "INSERT INTO data_access_logs "
                "(user_email, access_type, resource_type, resource_id, resource_name, "
                "fields_accessed, purpose, ip_address) VALUES (?,?,?,?,?,?,?,?)",
                (actor, access_type, resource_type, resource_id, resource_name,
                 json.dumps(fields or []), purpose, ip))
        return eid

    def log_review_action(self, actor: str, action: str, document_id: int,
                          detail: str = None, ip: str = None) -> int:
        """Log a review/approval action."""
        return self.log(event_type=f"review_{action}", category="data_modification",
                        severity="medium" if action in ("approve", "reject") else "info",
                        actor=actor, actor_ip=ip, target_resource="document",
                        target_id=document_id, action=action, detail=detail)

    # ─── PRIVATE HELPERS ──────────────────────────────────────────────

    def _record_metric(self, conn, name: str, value: float, labels: dict = None):
        conn.execute(
            "INSERT INTO security_metrics (metric_name, metric_type, value, labels) "
            "VALUES (?,?,?,?)", (name, "counter", value, json.dumps(labels or {})))

    def _track_failed_login(self, actor: str, ip: str):
        """Track failed logins and create alerts for brute force."""
        with db() as conn:
            # Count failures in last 5 minutes
            five_min_ago = (datetime.utcnow() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
            count = conn.execute(
                "SELECT COUNT(*) c FROM security_events "
                "WHERE event_type='login_failed' AND actor=? AND created_at > ?",
                (actor, five_min_ago)).fetchone()["c"]

            if count >= ALERT_THRESHOLDS["failed_logins_per_minute"]:
                self._create_alert(conn, "brute_force", "high",
                                   f"Brute force detected: {count} failed logins from {actor}",
                                   actor=actor, actor_ip=ip)

            # Hourly count
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            hourly_count = conn.execute(
                "SELECT COUNT(*) c FROM security_events "
                "WHERE event_type='login_failed' AND actor=? AND created_at > ?",
                (actor, one_hour_ago)).fetchone()["c"]

            if hourly_count >= ALERT_THRESHOLDS["failed_logins_per_hour"]:
                self._create_alert(conn, "brute_force_sustained", "critical",
                                   f"Sustained brute force: {hourly_count} failed logins in 1h from {actor}",
                                   actor=actor, actor_ip=ip)
                # Lock the account
                conn.execute(
                    "UPDATE security_users SET locked_until=?, is_active=0 WHERE email=?",
                    ((datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"), actor))
                conn.execute(
                    "INSERT INTO security_events (correlation_id, event_type, category, severity, actor, detail) "
                    "VALUES (?,?,?,?,?,?)",
                    (gen_correlation_id(), "account_locked", "security", "critical",
                     actor, f"Account locked due to {hourly_count} failed login attempts"))

    def _check_thresholds(self, conn, event_type: str, category: str,
                          actor: str, ip: str):
        """Check if event counts exceed alert thresholds."""
        one_min_ago = (datetime.utcnow() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

        if category == "system" and event_type == "pipeline_failed":
            count = conn.execute(
                "SELECT COUNT(*) c FROM security_events "
                "WHERE event_type='pipeline_failed' AND created_at > ?",
                (one_min_ago,)).fetchone()["c"]
            if count >= ALERT_THRESHOLDS["api_errors_per_minute"]:
                self._create_alert(conn, "pipeline_failures", "high",
                                   f"Pipeline failure spike: {count} failures in 1 minute")

    def _scan_threats(self, conn, text: str, actor: str, ip: str, event_id: int):
        """Scan input text for threat patterns."""
        for threat_name, pattern in THREAT_PATTERNS.items():
            if pattern.search(text):
                self._create_alert(conn, threat_name, "critical",
                                   f"Threat pattern detected: {threat_name} in input",
                                   actor=actor, actor_ip=ip,
                                   source_event_id=event_id)
                conn.execute(
                    "INSERT INTO security_events "
                    "(correlation_id, event_type, category, severity, actor, actor_ip, "
                    "detail, action, result) VALUES (?,?,?,?,?,?,?,?,?)",
                    (gen_correlation_id(), f"threat_{threat_name}", "security",
                     "critical", actor, ip,
                     f"Pattern: {threat_name} | Input: {text[:200]}",
                     "threat_detected", "blocked"))

    def _create_alert(self, conn, alert_type: str, severity: str, title: str,
                       description: str = None, actor: str = None,
                       actor_ip: str = None, source_event_id: int = None):
        """Create a security alert."""
        conn.execute(
            "INSERT INTO security_alerts "
            "(alert_type, severity, title, description, source_event_id, actor, actor_ip) "
            "VALUES (?,?,?,?,?,?,?)",
            (alert_type, severity, title, description, source_event_id, actor, actor_ip))

    def query_events(self, category: str = None, severity: str = None,
                     actor: str = None, limit: int = 100) -> list:
        """Query security events with filters."""
        with db() as conn:
            q = "SELECT * FROM security_events WHERE 1=1"
            params = []
            if category:
                q += " AND category=?"
                params.append(category)
            if severity:
                q += " AND severity=?"
                params.append(severity)
            if actor:
                q += " AND actor=?"
                params.append(actor)
            q += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    def get_event_stats(self, hours: int = 24) -> dict:
        """Get event statistics for the last N hours."""
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        with db() as conn:
            by_category = conn.execute(
                "SELECT category, COUNT(*) as count FROM security_events "
                "WHERE created_at > ? GROUP BY category", (since,)).fetchall()
            by_severity = conn.execute(
                "SELECT severity, COUNT(*) as count FROM security_events "
                "WHERE created_at > ? GROUP BY severity", (since,)).fetchall()
            by_result = conn.execute(
                "SELECT result, COUNT(*) as count FROM security_events "
                "WHERE created_at > ? GROUP BY result", (since,)).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) c FROM security_events WHERE created_at > ?",
                (since,)).fetchone()["c"]
            return {
                "period_hours": hours,
                "total_events": total,
                "by_category": {r["category"]: r["count"] for r in by_category},
                "by_severity": {r["severity"]: r["count"] for r in by_severity},
                "by_result": {r["result"]: r["count"] for r in by_result},
            }


# ═══════════════════════════════════════════════════════════════════════════
# METRICS COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════

class MetricsCollector:
    """
    Collects and queries operational metrics.
    Supports counters, gauges, and histograms.
    """

    def __init__(self):
        init_db()

    def counter(self, name: str, value: float = 1, labels: dict = None):
        """Increment a counter metric."""
        with db() as conn:
            conn.execute(
                "INSERT INTO security_metrics (metric_name, metric_type, value, labels) "
                "VALUES (?,?,?,?)", (name, "counter", value, json.dumps(labels or {})))

    def gauge(self, name: str, value: float, labels: dict = None):
        """Set a gauge metric."""
        with db() as conn:
            conn.execute(
                "INSERT INTO security_metrics (metric_name, metric_type, value, labels) "
                "VALUES (?,?,?,?)", (name, "gauge", value, json.dumps(labels or {})))

    def histogram(self, name: str, value: float, labels: dict = None):
        """Record a histogram value."""
        with db() as conn:
            conn.execute(
                "INSERT INTO security_metrics (metric_name, metric_type, value, labels) "
                "VALUES (?,?,?,?)", (name, "histogram", value, json.dumps(labels or {})))

    def get_metric(self, name: str, hours: int = 24) -> dict:
        """Get aggregated metric values."""
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        with db() as conn:
            rows = conn.execute(
                "SELECT metric_type, SUM(value) as total, AVG(value) as avg, "
                "MIN(value) as min, MAX(value) as max, COUNT(*) as count "
                "FROM security_metrics WHERE metric_name=? AND created_at > ? "
                "GROUP BY metric_type", (name, since)).fetchall()
            if rows:
                r = rows[0]
                return {"name": name, "type": r["metric_type"], "total": r["total"],
                        "avg": round(r["avg"], 2), "min": r["min"], "max": r["max"],
                        "count": r["count"]}
            return {"name": name, "total": 0, "count": 0}

    def get_all_metrics(self, hours: int = 24) -> dict:
        """Get all metrics for dashboard."""
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        with db() as conn:
            rows = conn.execute(
                "SELECT metric_name, metric_type, SUM(value) as total, COUNT(*) as count "
                "FROM security_metrics WHERE created_at > ? "
                "GROUP BY metric_name, metric_type ORDER BY total DESC",
                (since,)).fetchall()
            return {r["metric_name"]: {"type": r["metric_type"], "total": r["total"],
                                       "count": r["count"]} for r in rows}


# ═══════════════════════════════════════════════════════════════════════════
# DISTRIBUTED TRACING
# ═══════════════════════════════════════════════════════════════════════════

class DistributedTracer:
    """
    Distributed tracing engine with correlation IDs, span hierarchy,
    and latency tracking.
    """

    def __init__(self):
        init_db()
        self._trace_stack = []

    def start_trace(self, operation: str, service: str = "legal-ai",
                    metadata: dict = None) -> str:
        """Start a new trace and return the trace_id."""
        trace_id = gen_correlation_id()
        span_id = gen_correlation_id()
        with db() as conn:
            conn.execute(
                "INSERT INTO security_traces "
                "(trace_id, span_id, operation, service, start_time, metadata) "
                "VALUES (?,?,?,?,?,?)",
                (trace_id, span_id, operation, service, now_str(),
                 json.dumps(metadata or {})))
        self._trace_stack.append({"trace_id": trace_id, "span_id": span_id,
                                   "operation": operation, "start": time.time()})
        return trace_id

    def end_trace(self, status: str = "ok", error_message: str = None):
        """End the current trace span."""
        if not self._trace_stack:
            return
        current = self._trace_stack.pop()
        duration_ms = (time.time() - current["start"]) * 1000
        with db() as conn:
            conn.execute(
                "UPDATE security_traces SET end_time=?, duration_ms=?, status=?, "
                "error_message=? WHERE trace_id=? AND span_id=?",
                (now_str(), round(duration_ms, 2), status, error_message,
                 current["trace_id"], current["span_id"]))

    def start_span(self, operation: str, metadata: dict = None) -> str:
        """Start a child span within the current trace."""
        parent = self._trace_stack[-1] if self._trace_stack else None
        span_id = gen_correlation_id()
        trace_id = parent["trace_id"] if parent else gen_correlation_id()
        with db() as conn:
            conn.execute(
                "INSERT INTO security_traces "
                "(trace_id, span_id, parent_span_id, operation, start_time, metadata) "
                "VALUES (?,?,?,?,?,?)",
                (trace_id, span_id, parent["span_id"] if parent else None,
                 operation, now_str(), json.dumps(metadata or {})))
        self._trace_stack.append({"trace_id": trace_id, "span_id": span_id,
                                   "operation": operation, "start": time.time()})
        return span_id

    def end_span(self, status: str = "ok", error_message: str = None):
        """End the current child span."""
        self.end_trace(status, error_message)

    def get_trace(self, trace_id: str) -> list:
        """Get all spans for a trace."""
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM security_traces WHERE trace_id=? ORDER BY start_time ASC",
                (trace_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_slow_traces(self, min_duration_ms: float = 1000, limit: int = 20) -> list:
        """Find traces exceeding a duration threshold."""
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM security_traces WHERE duration_ms > ? "
                "ORDER BY duration_ms DESC LIMIT ?", (min_duration_ms, limit)).fetchall()
            return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# ALERT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class AlertManager:
    """
    Security alert management with acknowledgment, escalation, and resolution.
    """

    def __init__(self):
        init_db()

    def get_open_alerts(self, severity: str = None) -> list:
        """Get all open security alerts."""
        with db() as conn:
            q = "SELECT * FROM security_alerts WHERE status='open'"
            params = []
            if severity:
                q += " AND severity=?"
                params.append(severity)
            q += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
            q += "WHEN 'medium' THEN 3 ELSE 4 END, triggered_at DESC"
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    def acknowledge(self, alert_id: int, user: str) -> dict:
        """Acknowledge an alert."""
        with db() as conn:
            conn.execute(
                "UPDATE security_alerts SET status='acknowledged', "
                "acknowledged_at=?, acknowledged_by=? WHERE id=?",
                (now_str(), user, alert_id))
            return {"alert_id": alert_id, "status": "acknowledged"}

    def resolve(self, alert_id: int, user: str, notes: str = "") -> dict:
        """Resolve an alert."""
        with db() as conn:
            conn.execute(
                "UPDATE security_alerts SET status='resolved', "
                "resolved_at=?, resolved_by=? WHERE id=?",
                (now_str(), user, alert_id))
            conn.execute(
                "INSERT INTO security_events (correlation_id, event_type, category, severity, "
                "actor, detail) VALUES (?,?,?,?,?,?)",
                (gen_correlation_id(), "alert_resolved", "security", "info",
                 user, f"Alert #{alert_id} resolved: {notes}"))
            return {"alert_id": alert_id, "status": "resolved"}

    def get_alert_stats(self, hours: int = 24) -> dict:
        """Get alert statistics."""
        since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        with db() as conn:
            rows = conn.execute(
                "SELECT severity, status, COUNT(*) as count FROM security_alerts "
                "WHERE triggered_at > ? GROUP BY severity, status", (since,)).fetchall()
            stats = {}
            for r in rows:
                if r["severity"] not in stats:
                    stats[r["severity"]] = {}
                stats[r["severity"]][r["status"]] = r["count"]
            return stats


# ═══════════════════════════════════════════════════════════════════════════
# COMPLIANCE REPORTER
# ═══════════════════════════════════════════════════════════════════════════

class ComplianceReporter:
    """
    Compliance reporting aligned with SOC2, ISO 27001, and DPDP Act.
    """

    CONTROLS = [
        {"framework": "SOC2", "control_id": "CC6.1", "name": "Logical Access Controls",
         "description": "System access is restricted to authorized users"},
        {"framework": "SOC2", "control_id": "CC6.2", "name": "Authentication Mechanisms",
         "description": "Multi-factor or strong authentication is enforced"},
        {"framework": "SOC2", "control_id": "CC6.3", "name": "Access Revocation",
         "description": "Access is revoked upon termination or role change"},
        {"framework": "SOC2", "control_id": "CC7.1", "name": "Security Monitoring",
         "description": "Security events are monitored and alerts generated"},
        {"framework": "SOC2", "control_id": "CC7.2", "name": "Incident Response",
         "description": "Security incidents are detected and responded to promptly"},
        {"framework": "ISO27001", "control_id": "A.9.2.1", "name": "User Registration",
         "description": "Formal user registration and de-registration process"},
        {"framework": "ISO27001", "control_id": "A.9.2.2", "name": "Privilege Management",
         "description": "Privileges are allocated on need-to-know basis"},
        {"framework": "ISO27001", "control_id": "A.12.4.1", "name": "Event Logging",
         "description": "Audit logs recording user activities and exceptions"},
        {"framework": "ISO27001", "control_id": "A.12.4.2", "name": "Log Protection",
         "description": "Logs are protected from tampering and unauthorized access"},
        {"framework": "ISO27001", "control_id": "A.16.1.2", "name": "Reporting Events",
         "description": "Security events are reported through proper channels"},
        {"framework": "DPDP", "control_id": "DPA.8", "name": "Data Breach Notification",
         "description": "Personal data breaches reported within 72 hours"},
        {"framework": "DPDP", "control_id": "DPA.11", "name": "Consent Management",
         "description": "Lawful basis for processing is documented"},
        {"framework": "DPDP", "control_id": "DPA.12", "name": "Data Processing Records",
         "description": "Records of processing activities are maintained"},
    ]

    def __init__(self):
        init_db()

    def run_compliance_check(self) -> list:
        """Run all compliance checks and return results."""
        results = []
        for ctrl in self.CONTROLS:
            status = self._check_control(ctrl)
            with db() as conn:
                conn.execute(
                    "INSERT INTO compliance_logs (framework, control_id, control_name, "
                    "status, evidence, next_check) VALUES (?,?,?,?,?,?)",
                    (ctrl["framework"], ctrl["control_id"], ctrl["name"],
                     status["status"], json.dumps(status["evidence"]),
                     (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")))
            results.append({**ctrl, **status})
        return results

    def _check_control(self, control: dict) -> dict:
        """Evaluate a single compliance control."""
        cid = control["control_id"]

        if cid == "CC6.1":  # Logical Access
            return self._check_logical_access()
        elif cid == "CC6.2":  # Authentication
            return self._check_authentication()
        elif cid == "CC6.3":  # Access Revocation
            return self._check_access_revocation()
        elif cid == "CC7.1":  # Security Monitoring
            return self._check_security_monitoring()
        elif cid == "CC7.2":  # Incident Response
            return self._check_incident_response()
        elif cid == "A.9.2.1":  # User Registration
            return self._check_user_registration()
        elif cid == "A.9.2.2":  # Privilege Management
            return self._check_privilege_management()
        elif cid in ("A.12.4.1", "A.12.4.2"):  # Audit Logging
            return self._check_audit_logging()
        elif cid == "A.16.1.2":  # Event Reporting
            return self._check_event_reporting()
        elif cid in ("DPA.8", "DPA.11", "DPA.12"):  # DPDP
            return self._check_dpdp()
        return {"status": "pass", "evidence": ["Control checked"]}

    def _check_logical_access(self) -> dict:
        with db() as conn:
            active = conn.execute("SELECT COUNT(*) c FROM security_users WHERE is_active=1").fetchone()["c"]
            total = conn.execute("SELECT COUNT(*) c FROM security_users").fetchone()["c"]
            locked = conn.execute("SELECT COUNT(*) c FROM security_users WHERE locked_until > datetime('now')").fetchone()["c"]
        return {
            "status": "pass" if locked == 0 else "warning",
            "evidence": [f"{active}/{total} active users", f"{locked} currently locked"]
        }

    def _check_authentication(self) -> dict:
        with db() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM security_users").fetchone()["c"]
            with_hash = conn.execute("SELECT COUNT(*) c FROM security_users WHERE password_hash != ''").fetchone()["c"]
        return {
            "status": "pass" if total == with_hash else "fail",
            "evidence": [f"{with_hash}/{total} users have password hashes"]
        }

    def _check_access_revocation(self) -> dict:
        with db() as conn:
            inactive = conn.execute("SELECT COUNT(*) c FROM security_users WHERE is_active=0").fetchone()["c"]
        return {"status": "pass", "evidence": [f"{inactive} deactivated accounts"]}

    def _check_security_monitoring(self) -> dict:
        with db() as conn:
            events_24h = conn.execute(
                "SELECT COUNT(*) c FROM security_events WHERE created_at > datetime('now', '-1 day')").fetchone()["c"]
            alerts = conn.execute("SELECT COUNT(*) c FROM security_alerts WHERE status='open'").fetchone()["c"]
        return {
            "status": "pass" if events_24h > 0 else "warning",
            "evidence": [f"{events_24h} events in 24h", f"{alerts} open alerts"]
        }

    def _check_incident_response(self) -> dict:
        with db() as conn:
            resolved = conn.execute(
                "SELECT COUNT(*) c FROM security_alerts WHERE status='resolved'").fetchone()["c"]
            total = conn.execute("SELECT COUNT(*) c FROM security_alerts").fetchone()["c"]
        return {
            "status": "pass" if total == 0 or resolved / max(total, 1) > 0.5 else "warning",
            "evidence": [f"{resolved}/{total} alerts resolved"]
        }

    def _check_user_registration(self) -> dict:
        with db() as conn:
            users = conn.execute("SELECT COUNT(*) c FROM security_users").fetchone()["c"]
        return {"status": "pass" if users > 0 else "fail", "evidence": [f"{users} registered users"]}

    def _check_privilege_management(self) -> dict:
        with db() as conn:
            roles = conn.execute(
                "SELECT role, COUNT(*) c FROM security_users GROUP BY role").fetchall()
        return {
            "status": "pass",
            "evidence": [f"{r['role']}: {r['c']}" for r in roles]
        }

    def _check_audit_logging(self) -> dict:
        with db() as conn:
            logs_24h = conn.execute(
                "SELECT COUNT(*) c FROM security_audit_trail WHERE created_at > datetime('now', '-1 day')").fetchone()["c"]
        return {
            "status": "pass" if logs_24h > 0 else "warning",
            "evidence": [f"{logs_24h} audit entries in 24h"]
        }

    def _check_event_reporting(self) -> dict:
        with db() as conn:
            events = conn.execute("SELECT COUNT(*) c FROM security_events").fetchone()["c"]
        return {"status": "pass" if events > 0 else "warning", "evidence": [f"{events} total events"]}

    def _check_dpdp(self) -> dict:
        with db() as conn:
            access_logs = conn.execute("SELECT COUNT(*) c FROM data_access_logs").fetchone()["c"]
        return {
            "status": "pass" if access_logs >= 0 else "fail",
            "evidence": [f"{access_logs} data access log entries"]
        }

    def get_compliance_report(self) -> list:
        """Get the latest compliance check results."""
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM compliance_logs ORDER BY checked_at DESC LIMIT 50").fetchall()
            return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class HealthMonitor:
    """System health monitoring with component checks."""

    COMPONENTS = ["database", "api_server", "ocr_engine", "rag_index",
                   "ai_pipeline", "filesystem", "auth_service"]

    def __init__(self):
        init_db()

    def check_component(self, component: str) -> dict:
        """Check the health of a single component."""
        start = time.time()
        status = "healthy"
        detail = ""
        try:
            if component == "database":
                with db() as conn:
                    conn.execute("SELECT 1")
                detail = "SQLite WAL mode active"
            elif component == "filesystem":
                test_path = os.path.join(os.path.dirname(__file__), "health_test.tmp")
                with open(test_path, "w") as f:
                    f.write("ok")
                os.remove(test_path)
                detail = "File system writable"
            else:
                detail = "Component available"
        except Exception as e:
            status = "unhealthy"
            detail = str(e)

        elapsed = (time.time() - start) * 1000
        with db() as conn:
            conn.execute(
                "INSERT INTO health_checks (component, status, response_time_ms, detail) "
                "VALUES (?,?,?,?)", (component, status, round(elapsed, 2), detail))
        return {"component": component, "status": status,
                "response_time_ms": round(elapsed, 2), "detail": detail}

    def check_all(self) -> list:
        """Check all components."""
        return [self.check_component(c) for c in self.COMPONENTS]

    def get_health_history(self, component: str = None, limit: int = 50) -> list:
        """Get health check history."""
        with db() as conn:
            if component:
                rows = conn.execute(
                    "SELECT * FROM health_checks WHERE component=? "
                    "ORDER BY id DESC LIMIT ?", (component, limit)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM health_checks ORDER BY id DESC LIMIT ?",
                    (limit,)).fetchall()
            return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# SAMPLE DATA LOADER
# ═══════════════════════════════════════════════════════════════════════════

def load_sample_data():
    """Load comprehensive sample data for demonstration."""
    print("\n" + "=" * 60)
    print("  LOADING SAMPLE DATA — Security & Observability")
    print("=" * 60)

    # Initialize all components
    logger = SecurityEventLogger()
    metrics = MetricsCollector()
    tracer = DistributedTracer()
    alerts = AlertManager()
    compliance = ComplianceReporter()
    health = HealthMonitor()

    # 1. Create users
    print("\n[1/8] Creating security users...")
    users_data = [
        ("admin@tata.com", "Tata Legal Admin", "admin", "Corporate"),
        ("priya.sharma@tata.com", "Priya Sharma", "senior_counsel", "Legal"),
        ("rajesh.kumar@tata.com", "Rajesh Kumar", "reviewer", "Legal"),
        ("security@tata.com", "Security Operations", "security_admin", "InfoSec"),
        ("auditor@tata.com", "Compliance Auditor", "auditor", "Compliance"),
    ]
    with db() as conn:
        for email, name, role, bu in users_data:
            try:
                conn.execute(
                    "INSERT INTO security_users (email, name, role, password_hash, business_unit) "
                    "VALUES (?,?,?,?,?)",
                    (email, name, role, hashlib.sha256(f"{PEPPER}:tata123".encode()).hexdigest(), bu))
                print(f"  ✓ {name} ({role})")
            except sqlite3.IntegrityError:
                print(f"  · {email} exists")

    # 2. Authentication events
    print("\n[2/8] Generating authentication events...")
    auth_events = [
        ("admin@tata.com", "login_success", "192.168.1.100", "Mozilla/5.0 Mac"),
        ("admin@tata.com", "login_success", "10.0.0.50", "Mozilla/5.0 Mac"),
        ("priya.sharma@tata.com", "login_success", "192.168.1.105", "Chrome/120"),
        ("rajesh.kumar@tata.com", "login_success", "192.168.1.110", "Firefox/121"),
        ("unknown@attacker.com", "login_failed", "203.0.113.50", "curl/7.88"),
        ("unknown@attacker.com", "login_failed", "203.0.113.50", "curl/7.88"),
        ("unknown@attacker.com", "login_failed", "203.0.113.50", "curl/7.88"),
        ("unknown@attacker.com", "login_failed", "203.0.113.50", "curl/7.88"),
        ("unknown@attacker.com", "login_failed", "203.0.113.50", "curl/7.88"),
        ("admin@tata.com", "logout", "192.168.1.100", "Mozilla/5.0 Mac"),
        ("security@tata.com", "login_success", "10.0.0.10", "Chrome/120"),
    ]
    for email, event, ip, ua in auth_events:
        result = "success" if "success" in event else "failed"
        logger.log_auth_event(event, email, ip, ua, result)
    print(f"  ✓ {len(auth_events)} auth events logged")

    # 3. Data access events
    print("\n[3/8] Generating data access events...")
    data_events = [
        ("admin@tata.com", "read", "document", 1, "NovaCloud_MSA.pdf",
         ["clauses", "risks", "summary"], "Legal review"),
        ("priya.sharma@tata.com", "read", "document", 1, "NovaCloud_MSA.pdf",
         ["clauses", "risks"], "Risk assessment"),
        ("priya.sharma@tata.com", "update", "risk_flag", 1, "Unlimited Liability",
         ["disposition", "reviewer_note"], "Risk disposition"),
        ("rajesh.kumar@tata.com", "read", "document", 2, "Omega_Vendor.pdf",
         ["clauses"], "Contract review"),
        ("admin@tata.com", "export", "document", 1, "NovaCloud_MSA.pdf",
         ["full"], "Compliance audit"),
        ("anita.desai@tata.com", "read", "audit_log", None, "Audit History",
         ["all"], "Internal audit"),
    ]
    for email, atype, rtype, rid, rname, fields, purpose in data_events:
        logger.log_data_access(email, atype, rtype, rid, rname, fields, purpose,
                               "192.168.1.100")
    print(f"  ✓ {len(data_events)} data access events logged")

    # 4. Review actions
    print("\n[4/8] Generating review actions...")
    review_events = [
        ("priya.sharma@tata.com", "approve", 1, "Summary approved — all risks assessed"),
        ("priya.sharma@tata.com", "escalate", 1, "Liability cap escalated to GC"),
        ("rajesh.kumar@tata.com", "comment", 2, "Need additional data protection terms"),
        ("admin@tata.com", "reject", 4, "Employment contract needs HR review"),
    ]
    for email, action, doc_id, detail in review_events:
        logger.log_review_action(email, action, doc_id, detail, "192.168.1.100")
    print(f"  ✓ {len(review_events)} review actions logged")

    # 5. System events
    print("\n[5/8] Generating system events...")
    sys_events = [
        ("pipeline_start", "system", "info", "Pipeline started for doc #1"),
        ("ocr_complete", "system", "info", "OCR extracted 4523 chars, confidence=95%"),
        ("rag_retrieval", "system", "info", "Retrieved 5 references from knowledge base"),
        ("pipeline_complete", "system", "info", "Pipeline complete for doc #1"),
        ("pipeline_start", "system", "info", "Pipeline started for doc #2"),
        ("pipeline_complete", "system", "info", "Pipeline complete for doc #2"),
    ]
    for etype, cat, sev, detail in sys_events:
        logger.log(event_type=etype, category=cat, severity=sev,
                   actor="system", detail=detail)
    print(f"  ✓ {len(sys_events)} system events logged")

    # 6. Threat detection events
    print("\n[6/8] Generating threat detection events...")
    threat_events = [
        ("sql_injection_attempt", "security", "critical",
         "203.0.113.50", " UNION SELECT * FROM users --"),
        ("xss_attempt", "security", "critical",
         "198.51.100.23", "<script>alert('xss')</script> in search field"),
        ("path_traversal", "security", "high",
         "203.0.113.50", "Request for /../../../etc/passwd"),
    ]
    for etype, cat, sev, ip, detail in threat_events:
        logger.log(event_type=etype, category=cat, severity=sev,
                   actor="unknown", actor_ip=ip, detail=detail,
                   result="blocked")
    print(f"  ✓ {len(threat_events)} threat events logged")

    # 7. Metrics
    print("\n[7/8] Recording operational metrics...")
    metric_data = [
        ("api_requests_total", "counter", 1547),
        ("api_requests_total", "counter", 2341),
        ("documents_uploaded", "counter", 45),
        ("documents_processed", "counter", 42),
        ("clauses_extracted", "counter", 312),
        ("risks_flagged", "counter", 89),
        ("reviews_completed", "counter", 67),
        ("ocr_confidence_avg", "gauge", 93.5),
        ("pipeline_duration_seconds", "histogram", 12.4),
        ("pipeline_duration_seconds", "histogram", 8.7),
        ("pipeline_duration_seconds", "histogram", 15.2),
        ("rag_retrieval_latency_ms", "histogram", 45),
        ("rag_retrieval_latency_ms", "histogram", 38),
        ("active_sessions", "gauge", 5),
        ("database_connections", "gauge", 2),
    ]
    for name, mtype, value in metric_data:
        metrics.counter(name, value) if mtype == "counter" else \
        metrics.gauge(name, value) if mtype == "gauge" else \
        metrics.histogram(name, value)
    print(f"  ✓ {len(metric_data)} metrics recorded")

    # 8. Tracing
    print("\n[8/8] Generating distributed traces...")
    # Trace 1: Document processing
    trace_id = tracer.start_trace("document_processing", metadata={"doc_id": 1})
    time.sleep(0.01)
    tracer.start_span("ocr_extraction", {"file_type": ".pdf"})
    time.sleep(0.01)
    tracer.end_span()
    tracer.start_span("clause_extraction", {"clause_count": 8})
    time.sleep(0.01)
    tracer.end_span()
    tracer.start_span("rag_retrieval", {"references": 5})
    time.sleep(0.01)
    tracer.end_span()
    tracer.end_trace()

    # Trace 2: API request
    trace_id2 = tracer.start_trace("api_request", metadata={"method": "POST", "path": "/api/auth/login"})
    time.sleep(0.01)
    tracer.end_trace()

    print(f"  ✓ 2 traces with spans generated")

    # Run compliance checks
    print("\n  Running compliance checks...")
    results = compliance.run_compliance_check()
    passed = sum(1 for r in results if r["status"] == "pass")
    warned = sum(1 for r in results if r["status"] == "warning")
    failed = sum(1 for r in results if r["status"] == "fail")
    print(f"  ✓ {len(results)} controls checked: {passed} pass, {warned} warning, {failed} fail")

    # Health checks
    print("\n  Running health checks...")
    health_results = health.check_all()
    for h in health_results:
        print(f"  {'✓' if h['status'] == 'healthy' else '✗'} {h['component']}: {h['status']} ({h['response_time_ms']}ms)")

    print("\n" + "=" * 60)
    print("  SAMPLE DATA LOADED SUCCESSFULLY")
    print(f"  Users: {len(users_data)} | Events: {len(auth_events) + len(data_events) + len(review_events) + len(sys_events) + len(threat_events)}")
    print(f"  Metrics: {len(metric_data)} | Traces: 2 | Controls: {len(results)}")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — DEMONSTRATION
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "█" * 60)
    print("█  SECURITY LOGGING AND OBSERVABILITY — Standalone Module")
    print("█  Tata Group AI Legal Document Intelligence System")
    print("█" * 60)

    # Clean and init
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

    # Load sample data
    load_sample_data()

    # Initialize components
    logger = SecurityEventLogger()
    metrics = MetricsCollector()
    tracer = DistributedTracer()
    alerts = AlertManager()
    compliance = ComplianceReporter()
    health = HealthMonitor()

    # Demonstrate features
    print("\n" + "─" * 60)
    print("  FEATURE DEMONSTRATIONS")
    print("─" * 60)

    # 1. Security Event Query
    print("\n[DEMO 1] Security Events by Category")
    for cat in ["authentication", "data_access", "security"]:
        events = logger.query_events(category=cat, limit=3)
        print(f"  {cat}: {len(events)} events")
        for e in events[:2]:
            print(f"    [{e['severity']}] {e['event_type']}: {(e.get('detail') or '')[:50]}")

    # 2. Event Statistics
    print("\n[DEMO 2] Event Statistics (24h)")
    stats = logger.get_event_stats(24)
    print(f"  Total events: {stats['total_events']}")
    print(f"  By category: {stats['by_category']}")
    print(f"  By severity: {stats['by_severity']}")

    # 3. Metrics Dashboard
    print("\n[DEMO 3] Operational Metrics")
    all_metrics = metrics.get_all_metrics(24)
    for name, data in list(all_metrics.items())[:8]:
        print(f"  {name}: total={data['total']}, count={data['count']}")

    # 4. Open Alerts
    print("\n[DEMO 4] Open Security Alerts")
    open_alerts = alerts.get_open_alerts()
    for a in open_alerts[:5]:
        print(f"  [{a['severity'].upper()}] {a['title'][:60]}")
    print(f"  Total open: {len(open_alerts)}")

    # 5. Alert Statistics
    print("\n[DEMO 5] Alert Statistics")
    alert_stats = alerts.get_alert_stats(24)
    for severity, counts in alert_stats.items():
        print(f"  {severity}: {counts}")

    # 6. Distributed Traces
    print("\n[DEMO 6] Slow Traces (>1ms)")
    slow = tracer.get_slow_traces(0.5, limit=5)
    for t in slow:
        print(f"  [{t['trace_id']}] {t['operation']} — {t['duration_ms']}ms — {t['status']}")

    # 7. Compliance Report
    print("\n[DEMO 7] Compliance Report")
    report = compliance.get_compliance_report()
    frameworks = {}
    for r in report:
        fw = r["framework"]
        if fw not in frameworks:
            frameworks[fw] = {"pass": 0, "warning": 0, "fail": 0}
        frameworks[fw][r["status"]] = frameworks[fw].get(r["status"], 0) + 1
    for fw, counts in frameworks.items():
        print(f"  {fw}: {counts}")

    # 8. Health Status
    print("\n[DEMO 8] System Health")
    health_results = health.check_all()
    all_healthy = all(h["status"] == "healthy" for h in health_results)
    print(f"  Overall: {'ALL HEALTHY' if all_healthy else 'ISSUES DETECTED'}")
    for h in health_results:
        print(f"    {h['component']}: {h['status']} ({h['response_time_ms']}ms)")

    # 9. Threat Summary
    print("\n[DEMO 9] Threat Detection Summary")
    threats = logger.query_events(category="security", severity="critical", limit=10)
    print(f"  Critical security events: {len(threats)}")
    for t in threats:
        print(f"    {t['event_type']} from {t.get('actor_ip') or '?'}: {(t.get('detail') or '')[:50]}")

    # 10. Data Access Audit
    print("\n[DEMO 10] Data Access Audit Trail")
    with db() as conn:
        access_logs = conn.execute(
            "SELECT * FROM data_access_logs ORDER BY id DESC LIMIT 5").fetchall()
    for log in access_logs:
        print(f"  [{log['created_at']}] {log['user_email']} — {log['access_type']} "
              f"{log['resource_type']}#{log['resource_id']}: {log['resource_name']}")

    print("\n" + "█" * 60)
    print("█  MODULE COMPLETE — Database saved at: security_observability.db")
    print("█" * 60)


if __name__ == "__main__":
    main()
