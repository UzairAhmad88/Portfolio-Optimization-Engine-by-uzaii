"""
Regression and unit test suite for Session 98 Staging Readiness Preflight Harness.

Covers all 12 required scenarios from Session 98:
1. Missing required configuration.
2. Missing or insecure production secrets.
3. Development-only SQLite configuration in production.
4. Valid production configuration.
5. Missing Docker Compose executable.
6. Invalid Compose configuration.
7. Missing external staging endpoint or TLS evidence.
8. Backup and restore not actually verified.
9. Secret redaction in output.
10. Correct aggregation of PASS, FAIL, BLOCKED, WARNING, and NOT APPLICABLE states.
11. A mandatory failed check prevents a ready-for-review verdict.
12. A blocked external check cannot be misreported as verified.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ops.staging_preflight import (
    CheckStatus,
    OverallVerdict,
    PreflightCheck,
    PreflightReport,
    StagingPreflightRunner,
    format_report_console,
    redact_sensitive_text,
)


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Creates a synthetic repository root populated with standard configuration files."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "docker-compose.yml").write_text(
        """services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:?ERROR: POSTGRES_PASSWORD must be explicitly provided in environment or .env file}"
    ports:
      - "127.0.0.1:5432:5432"
  backend:
    environment:
      DATABASE_URL: "${DATABASE_URL:-postgresql+psycopg://quant_user:${POSTGRES_PASSWORD:?ERROR: POSTGRES_PASSWORD must be explicitly provided in environment or .env file}@postgres:5432/quant_portfolio_db}"
    ports:
      - "127.0.0.1:8000:8000"
  frontend:
    ports:
      - "80:80"
""",
        encoding="utf-8",
    )
    (root / ".env.example").write_text("APP_ENV=development\nPOSTGRES_PASSWORD=\n", encoding="utf-8")
    (root / ".gitignore").write_text(".env\n__pycache__/\n", encoding="utf-8")

    backend_dir = root / "backend"
    backend_dir.mkdir()
    (backend_dir / ".env.example").write_text("APP_ENV=development\n", encoding="utf-8")
    (backend_dir / "entrypoint.sh").write_text("#!/bin/sh\nalembic upgrade head\n", encoding="utf-8")

    frontend_dir = root / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "nginx.conf").write_text("server { listen 80; }\n", encoding="utf-8")

    docs_dir = root / "docs"
    docs_dir.mkdir()
    (docs_dir / "OPERATIONS_RUNBOOK.md").write_text(
        "# Runbook\nUpstream Reverse Proxy (TLS)\npg_dump -U quant_user quant_portfolio_db\npsql -U quant_user -d quant_portfolio_db\n",
        encoding="utf-8",
    )

    github_workflows = root / ".github" / "workflows"
    github_workflows.mkdir(parents=True)
    (github_workflows / "ci.yml").write_text("migration_head: e5f6a7b8c9d0\n", encoding="utf-8")

    return root


# -----------------------------------------------------------------------------
# Scenario 1: Missing required configuration
# -----------------------------------------------------------------------------
def test_missing_required_configuration_files(repo_root: Path):
    # Remove docker-compose.yml
    (repo_root / "docker-compose.yml").unlink()

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_a1 = next(c for c in report.checks if c.id == "A1_CONFIG_FILES_EXIST")
    assert chk_a1.status == CheckStatus.FAIL
    assert chk_a1.is_mandatory is True
    assert "docker-compose.yml" in chk_a1.evidence
    assert report.verdict == OverallVerdict.FAIL


# -----------------------------------------------------------------------------
# Scenario 2: Missing or insecure production secrets
# -----------------------------------------------------------------------------
def test_missing_or_insecure_production_secrets(repo_root: Path):
    with patch.dict(os.environ, {"APP_ENV": "production", "JWT_SECRET_KEY": "secret", "DATABASE_URL": ""}):
        from app.auth.security import validate_jwt_configuration

        with pytest.raises(RuntimeError):
            validate_jwt_configuration()

        runner = StagingPreflightRunner(repo_root=repo_root)
        report = runner.run_all()

        chk_b1 = next(c for c in report.checks if c.id == "B1_PROD_SECRETS_FAIL_CLOSED")
        assert chk_b1.status == CheckStatus.PASS  # Confirmed that fail-closed logic works

        chk_b3 = next(c for c in report.checks if c.id == "B3_JWT_SECRET_STRENGTH_POLICY")
        assert chk_b3.status == CheckStatus.PASS  # Verified policy rejects "secret"


# -----------------------------------------------------------------------------
# Scenario 3: Development-only SQLite configuration in production
# -----------------------------------------------------------------------------
def test_development_sqlite_in_production_rejected(repo_root: Path):
    with patch.dict(os.environ, {"APP_ENV": "production", "DATABASE_URL": "sqlite:///test.db"}):
        from app.db.session import validate_database_configuration

        with pytest.raises(RuntimeError, match="PostgreSQL is mandatory in production; SQLite cannot be used"):
            validate_database_configuration()

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()
    chk_c1 = next(c for c in report.checks if c.id == "C1_PROD_SQLITE_PROHIBITED")
    assert chk_c1.status == CheckStatus.PASS


# -----------------------------------------------------------------------------
# Scenario 4: Valid production configuration
# -----------------------------------------------------------------------------
def test_valid_production_configuration_accepted(repo_root: Path):
    valid_jwt = "8f7c9e1d2b3a4c5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e"
    valid_db_url = "postgresql+psycopg://quant_user:SecureStagingPass123!@localhost:5432/quant_portfolio_db"

    with patch.dict(os.environ, {"APP_ENV": "production", "JWT_SECRET_KEY": valid_jwt, "DATABASE_URL": valid_db_url}):
        from app.auth.security import validate_production_configuration

        validate_production_configuration()  # Should not raise

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()
    chk_b1 = next(c for c in report.checks if c.id == "B1_PROD_SECRETS_FAIL_CLOSED")
    assert chk_b1.status == CheckStatus.PASS


# -----------------------------------------------------------------------------
# Scenario 5: Missing Docker Compose executable
# -----------------------------------------------------------------------------
def test_missing_docker_compose_executable_reported_as_blocked(repo_root: Path):
    with patch("shutil.which", return_value=None):
        runner = StagingPreflightRunner(repo_root=repo_root)
        report = runner.run_all()

        chk_a3 = next(c for c in report.checks if c.id == "A3_DOCKER_CLI_AVAILABLE")
        assert chk_a3.status == CheckStatus.BLOCKED
        assert chk_a3.is_mandatory is True
        assert "not found on system PATH" in chk_a3.evidence


# -----------------------------------------------------------------------------
# Scenario 6: Invalid Compose configuration
# -----------------------------------------------------------------------------
def test_invalid_compose_configuration_fails(repo_root: Path):
    # Corrupt docker-compose.yml with invalid YAML syntax
    (repo_root / "docker-compose.yml").write_text("services: { unclosed_bracket", encoding="utf-8")

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_a4 = next(c for c in report.checks if c.id == "A4_COMPOSE_SYNTAX_VALID")
    assert chk_a4.status == CheckStatus.FAIL
    assert report.verdict == OverallVerdict.FAIL


# -----------------------------------------------------------------------------
# Scenario 7: Missing external staging endpoint or TLS evidence
# -----------------------------------------------------------------------------
def test_missing_external_staging_endpoint_reported_as_blocked(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root, staging_url=None)
    report = runner.run_all()

    chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
    assert chk_d3.status == CheckStatus.BLOCKED
    assert chk_d3.is_mandatory is True
    assert "not been provisioned" in chk_d3.evidence


def test_non_https_staging_url_fails(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root, staging_url="http://insecure.staging.local")
    report = runner.run_all()

    chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
    assert chk_d3.status == CheckStatus.FAIL
    assert "does not use HTTPS scheme" in chk_d3.evidence


# -----------------------------------------------------------------------------
# Scenario 8: Backup and restore not actually verified
# -----------------------------------------------------------------------------
def test_backup_and_restore_not_verified_reported_as_blocked(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root, live_db_verified=False)
    report = runner.run_all()

    chk_c4 = next(c for c in report.checks if c.id == "C4_LIVE_BACKUP_RESTORE_VERIFIED")
    assert chk_c4.status == CheckStatus.BLOCKED
    assert chk_c4.is_mandatory is True
    assert "Live staging database has not been provisioned" in chk_c4.evidence


# -----------------------------------------------------------------------------
# Scenario 9: Secret redaction in output
# -----------------------------------------------------------------------------
def test_secret_redaction_in_output():
    secret_pass = "SuperSecretDbPassword123!"
    secret_jwt = "8f7c9e1d2b3a4c5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e"
    raw_text = (
        f"Connecting with POSTGRES_PASSWORD={secret_pass} and "
        f"JWT_SECRET_KEY={secret_jwt} to postgresql+psycopg://user:{secret_pass}@localhost:5432/db"
    )

    sanitized = redact_sensitive_text(raw_text, [secret_pass, secret_jwt])

    assert secret_pass not in sanitized
    assert secret_jwt not in sanitized
    assert "***REDACTED***" in sanitized


# -----------------------------------------------------------------------------
# Scenario 10: Correct aggregation of PASS, FAIL, BLOCKED, WARNING, NOT_APPLICABLE
# -----------------------------------------------------------------------------
def test_aggregation_of_check_statuses(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    counts = report.summary_counts
    assert "PASS" in counts
    assert "FAIL" in counts
    assert "BLOCKED" in counts
    assert "WARNING" in counts
    assert "NOT_APPLICABLE" in counts

    total_counted = sum(counts.values())
    assert total_counted == len(report.checks)
    assert counts["PASS"] >= 10
    assert counts["BLOCKED"] >= 1
    assert counts["WARNING"] >= 1


# -----------------------------------------------------------------------------
# Scenario 11: Mandatory failed check prevents ready-for-review verdict
# -----------------------------------------------------------------------------
def test_mandatory_failed_check_prevents_ready_verdict(repo_root: Path):
    # Break a mandatory check: remove .gitignore
    (repo_root / ".gitignore").unlink()

    # Even if Docker is available and live staging URL is mocked
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_url.return_value.__enter__.return_value = mock_resp

        runner = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url="https://staging.test.internal",
            live_db_verified=True,
        )
        report = runner.run_all()

        chk_b5 = next(c for c in report.checks if c.id == "B5_ENV_FILE_GITIGNORED")
        assert chk_b5.status == CheckStatus.FAIL

        # Mandatory failure MUST cause overall FAIL
        assert report.verdict == OverallVerdict.FAIL


# -----------------------------------------------------------------------------
# Scenario 12: Blocked external check cannot be misreported as verified
# -----------------------------------------------------------------------------
def test_blocked_external_check_cannot_be_misreported_as_verified(repo_root: Path):
    # Without live staging URL or live db verification
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run") as mock_subproc:
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = ""
        mock_res.stderr = ""
        mock_subproc.return_value = mock_res

        runner = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url=None,
            live_db_verified=False,
        )
        report = runner.run_all()

        # External checks must be BLOCKED
        chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
        chk_c4 = next(c for c in report.checks if c.id == "C4_LIVE_BACKUP_RESTORE_VERIFIED")
        assert chk_d3.status == CheckStatus.BLOCKED
        assert chk_c4.status == CheckStatus.BLOCKED

        # Overall verdict MUST be BLOCKED, never READY
        assert report.verdict == OverallVerdict.BLOCKED
        assert report.verdict != OverallVerdict.READY


# -----------------------------------------------------------------------------
# Scenario 13: Ready verdict when all prerequisites and probes are verified
# -----------------------------------------------------------------------------
def test_ready_verdict_when_all_prerequisites_and_probes_verified(repo_root: Path):
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run") as mock_subproc, \
         patch("urllib.request.urlopen") as mock_url:
        # Mock git and compose
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = ""
        mock_res.stderr = ""
        mock_subproc.return_value = mock_res

        # Mock HTTPS probe
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_url.return_value.__enter__.return_value = mock_resp

        runner = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url="https://staging.quantengine.internal",
            live_db_verified=True,
        )
        report = runner.run_all()

        # All mandatory checks should PASS
        mandatory_statuses = [c.status for c in report.checks if c.is_mandatory]
        assert all(s == CheckStatus.PASS for s in mandatory_statuses)
        assert report.verdict == OverallVerdict.READY


# -----------------------------------------------------------------------------
# Scenario 14: Report formatting and JSON conversion
# -----------------------------------------------------------------------------
def test_report_formatting_and_json(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    formatted_text = format_report_console(report)
    assert "STAGING READINESS PREFLIGHT HARNESS" in formatted_text
    assert "PREFLIGHT SUMMARY COUNTS:" in formatted_text
    assert report.verdict.value in formatted_text

    report_dict = report.to_dict()
    assert report_dict["verdict"] == report.verdict.value
    assert len(report_dict["checks"]) == len(report.checks)


# =============================================================================
# SESSION 99 AUDIT REGRESSION TESTS (DEFECT-99-01 through DEFECT-99-08)
# =============================================================================

# -----------------------------------------------------------------------------
# Audit Test 1: Verdict Precedence & Fail-Closed Rules
# -----------------------------------------------------------------------------
def test_empty_checks_fails_closed():
    """An empty or uninitialized checks list must fail closed deterministically."""
    runner = StagingPreflightRunner()
    runner.checks = []
    # If run_all is called on runner with empty checks
    with patch.object(runner, "_check_category_a_repository"), \
         patch.object(runner, "_check_category_b_secrets"), \
         patch.object(runner, "_check_category_c_database"), \
         patch.object(runner, "_check_category_d_network"), \
         patch.object(runner, "_check_category_e_operational_safeguards"):
        report = runner.run_all()
        assert report.verdict == OverallVerdict.FAIL


def test_verdict_mandatory_fail_precedence_over_blocked():
    """Mandatory FAIL must take absolute precedence over BLOCKED."""
    runner = StagingPreflightRunner()
    with patch.object(runner, "_check_category_a_repository", lambda: runner.checks.append(
        PreflightCheck(id="CHK1", category="Cat", title="Mandatory Fail", status=CheckStatus.FAIL, is_mandatory=True, evidence="Failed")
    )), patch.object(runner, "_check_category_b_secrets", lambda: runner.checks.append(
        PreflightCheck(id="CHK2", category="Cat", title="Mandatory Blocked", status=CheckStatus.BLOCKED, is_mandatory=True, evidence="Blocked")
    )), patch.object(runner, "_check_category_c_database", lambda: None), \
       patch.object(runner, "_check_category_d_network", lambda: None), \
       patch.object(runner, "_check_category_e_operational_safeguards", lambda: None):
        report = runner.run_all()
        assert report.verdict == OverallVerdict.FAIL


def test_verdict_mandatory_warning_causes_fail():
    """A mandatory check that evaluates to WARNING must escalate to FAIL."""
    runner = StagingPreflightRunner()
    with patch.object(runner, "_check_category_a_repository", lambda: runner.checks.append(
        PreflightCheck(id="CHK1", category="Cat", title="Mandatory Warning", status=CheckStatus.WARNING, is_mandatory=True, evidence="Warning on mandatory")
    )), patch.object(runner, "_check_category_b_secrets", lambda: None), \
       patch.object(runner, "_check_category_c_database", lambda: None), \
       patch.object(runner, "_check_category_d_network", lambda: None), \
       patch.object(runner, "_check_category_e_operational_safeguards", lambda: None):
        report = runner.run_all()
        assert report.verdict == OverallVerdict.FAIL


def test_strict_mode_escalates_advisory_warning_to_fail(repo_root: Path):
    """In --strict mode, advisory warnings escalate to FAIL; in non-strict mode they remain visible."""
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run") as mock_subproc, \
         patch("urllib.request.urlopen") as mock_url:
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_subproc.return_value = mock_res
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_url.return_value.__enter__.return_value = mock_resp

        # Non-strict mode: Advisory warnings (e.g. E3, E4, E5, E7) allow READY
        runner_normal = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url="https://staging.quantengine.internal",
            live_db_verified=True,
            strict=False,
        )
        report_normal = runner_normal.run_all()
        assert report_normal.verdict == OverallVerdict.READY

        # Strict mode: Advisory warnings cause overall FAIL
        runner_strict = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url="https://staging.quantengine.internal",
            live_db_verified=True,
            strict=True,
        )
        report_strict = runner_strict.run_all()
        assert report_strict.verdict == OverallVerdict.FAIL


# -----------------------------------------------------------------------------
# Audit Test 2: Quoted Secret Masking & URI Variations
# -----------------------------------------------------------------------------
def test_redact_quoted_secrets_and_various_uris():
    """Verify redaction handles quoted values, connection strings, bearer tokens, and JWTs."""
    raw = (
        'POSTGRES_PASSWORD="my_quoted_password_123"\n'
        "POSTGRES_PASSWORD='single_quoted_password_456'\n"
        "DATABASE_URL=postgresql://quant_admin:db_pass_789@db-host:5432/quant_portfolio_db\n"
        "DATABASE_URL=postgresql+psycopg://app_user:psycopg_pass_abc@localhost:5432/prod_db\n"
        "Connecting to postgresql://raw_user:raw_pass_xyz@10.0.0.5:5432/data\n"
        "Authorization: Bearer header.payload.signature_xyz\n"
        "Found token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c\n"
    )
    redacted = redact_sensitive_text(raw)

    assert "my_quoted_password_123" not in redacted
    assert "single_quoted_password_456" not in redacted
    assert "db_pass_789" not in redacted
    assert "psycopg_pass_abc" not in redacted
    assert "raw_pass_xyz" not in redacted
    assert "header.payload.signature_xyz" not in redacted
    assert "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" not in redacted

    assert 'POSTGRES_PASSWORD="***REDACTED***"' in redacted
    assert "POSTGRES_PASSWORD='***REDACTED***'" in redacted
    assert "DATABASE_URL=***REDACTED***" in redacted
    assert "Connecting to postgresql://raw_user:***REDACTED***@10.0.0.5:5432/data" in redacted


# -----------------------------------------------------------------------------
# Audit Test 3: Operator Attestation Evidence Clarity (C4)
# -----------------------------------------------------------------------------
def test_c4_live_backup_restore_attestation_clarity(repo_root: Path):
    """When live_db_verified is True, report must explicitly state it is a manual attestation."""
    runner = StagingPreflightRunner(repo_root=repo_root, live_db_verified=True)
    report = runner.run_all()

    chk_c4 = next(c for c in report.checks if c.id == "C4_LIVE_BACKUP_RESTORE_VERIFIED")
    assert chk_c4.status == CheckStatus.PASS
    assert "Operator Attested" in chk_c4.title
    assert "MANUAL ATTESTATION" in chk_c4.evidence
    assert "Not independently automated by preflight runner" in chk_c4.evidence


# -----------------------------------------------------------------------------
# Audit Test 4: Structured YAML Port Isolation Auditing (D1)
# -----------------------------------------------------------------------------
def test_port_isolation_rejects_unbound_and_public_ports(repo_root: Path):
    """Structured YAML parsing in D1 must reject 0.0.0.0 or unbounded host ports."""
    # Write a compose file exposing postgres to 0.0.0.0
    (repo_root / "docker-compose.yml").write_text(
        """services:
  postgres:
    ports:
      - "0.0.0.0:5432:5432"
  backend:
    ports:
      - "127.0.0.1:8000:8000"
""",
        encoding="utf-8",
    )
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_d1 = next(c for c in report.checks if c.id == "D1_COMPOSE_PORT_ISOLATION")
    assert chk_d1.status == CheckStatus.FAIL
    assert "postgres_isolated=False" in chk_d1.evidence


def test_port_isolation_rejects_unprefixed_ports(repo_root: Path):
    """Compose file with '5432:5432' without host prefix must fail D1."""
    (repo_root / "docker-compose.yml").write_text(
        """services:
  postgres:
    ports:
      - "5432:5432"
  backend:
    ports:
      - "127.0.0.1:8000:8000"
""",
        encoding="utf-8",
    )
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_d1 = next(c for c in report.checks if c.id == "D1_COMPOSE_PORT_ISOLATION")
    assert chk_d1.status == CheckStatus.FAIL


# -----------------------------------------------------------------------------
# Audit Test 5: Subprocess Timeout & Exception Safety (A2, A4)
# -----------------------------------------------------------------------------
def test_git_diff_timeout_fails_safely(repo_root: Path):
    """Subprocess timeout on git diff must be caught and recorded as FAIL."""
    import subprocess
    (repo_root / ".git").mkdir()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["git", "diff", "--check"], timeout=30.0)):
        runner = StagingPreflightRunner(repo_root=repo_root)
        report = runner.run_all()

        chk_a2 = next(c for c in report.checks if c.id == "A2_GIT_DIFF_CHECK")
        assert chk_a2.status == CheckStatus.FAIL
        assert "timed out after 30 seconds" in chk_a2.evidence


def test_compose_syntax_timeout_fails_safely(repo_root: Path):
    """Subprocess timeout on docker compose config must be caught and recorded as FAIL."""
    import subprocess
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["docker", "compose", "config"], timeout=30.0)):
        runner = StagingPreflightRunner(repo_root=repo_root)
        report = runner.run_all()

        chk_a4 = next(c for c in report.checks if c.id == "A4_COMPOSE_SYNTAX_VALID")
        assert chk_a4.status == CheckStatus.FAIL
        assert "timed out after 30 seconds" in chk_a4.evidence


def test_compose_syntax_cli_error_fails_mandatory_a4(repo_root: Path):
    """Unexpected exception in docker compose config must record FAIL (not WARNING) on mandatory A4."""
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run", side_effect=RuntimeError("Docker daemon socket closed unexpectedly")):
        runner = StagingPreflightRunner(repo_root=repo_root)
        report = runner.run_all()

        chk_a4 = next(c for c in report.checks if c.id == "A4_COMPOSE_SYNTAX_VALID")
        assert chk_a4.status == CheckStatus.FAIL
        assert chk_a4.is_mandatory is True
        assert "Docker daemon socket closed unexpectedly" in chk_a4.evidence


# -----------------------------------------------------------------------------
# Audit Test 6: Staging URL Probe Integrity & Synchronization (D3 & E1)
# -----------------------------------------------------------------------------
def test_d3_malformed_or_non_https_url_fails(repo_root: Path):
    """Invalid URL structures or schemes without hostname fail D3."""
    runner = StagingPreflightRunner(repo_root=repo_root, staging_url="https://")
    report = runner.run_all()
    chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
    assert chk_d3.status == CheckStatus.FAIL


def test_d3_probe_http_500_fails_mandatory_d3(repo_root: Path):
    """HTTP 500 error from staging probe must result in CheckStatus.FAIL."""
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 500
        mock_url.return_value.__enter__.return_value = mock_resp

        runner = StagingPreflightRunner(repo_root=repo_root, staging_url="https://staging.test.internal")
        report = runner.run_all()

        chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
        assert chk_d3.status == CheckStatus.FAIL
        assert chk_d3.is_mandatory is True
        assert "returned unexpected HTTP status 500" in chk_d3.evidence


def test_d3_probe_http_401_verifies_tls(repo_root: Path):
    """HTTP 401 Basic Auth on staging gateway still verifies that TLS certificate handshake succeeded."""
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        url="https://staging.test.internal", code=401, msg="Unauthorized", hdrs={}, fp=None
    )):
        runner = StagingPreflightRunner(repo_root=repo_root, staging_url="https://staging.test.internal")
        report = runner.run_all()

        chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
        assert chk_d3.status == CheckStatus.PASS
        assert "TLS certificate verified" in chk_d3.evidence


def test_e1_synchronization_with_d3_failure(repo_root: Path):
    """When D3 probe fails, E1 (OPS-95-01) must FAIL rather than falsely reporting PASS."""
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused: [Errno 111]")):
        runner = StagingPreflightRunner(repo_root=repo_root, staging_url="https://offline.staging.internal")
        report = runner.run_all()

        chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
        chk_e1 = next(c for c in report.checks if c.id == "E1_RISK_OPS_95_01_EDGE_TLS")

        assert chk_d3.status == CheckStatus.FAIL
        assert chk_e1.status == CheckStatus.FAIL  # Synchronized! Never false-PASS
        assert "Upstream reverse proxy probe failed" in chk_e1.evidence


# -----------------------------------------------------------------------------
# Audit Test 7: Mandatory Check Failure Classification (C3, D2)
# -----------------------------------------------------------------------------
def test_missing_backup_commands_in_runbook_fails_c3(repo_root: Path):
    """Runbook missing backup commands must FAIL mandatory C3."""
    (repo_root / "docs" / "OPERATIONS_RUNBOOK.md").write_text("# Incomplete Runbook\n", encoding="utf-8")
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_c3 = next(c for c in report.checks if c.id == "C3_BACKUP_COMMAND_ALIGNMENT")
    assert chk_c3.status == CheckStatus.FAIL
    assert chk_c3.is_mandatory is True


def test_missing_tls_documentation_in_runbook_fails_d2(repo_root: Path):
    """Runbook missing TLS reverse proxy documentation must FAIL mandatory D2."""
    (repo_root / "docs" / "OPERATIONS_RUNBOOK.md").write_text(
        "# Runbook\npg_dump -U quant_user quant_portfolio_db\npsql -U quant_user -d quant_portfolio_db\n",
        encoding="utf-8",
    )
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_d2 = next(c for c in report.checks if c.id == "D2_UPSTREAM_TLS_DOCUMENTED")
    assert chk_d2.status == CheckStatus.FAIL
    assert chk_d2.is_mandatory is True
