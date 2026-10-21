"""
Comprehensive Deterministic and Mathematical Verification Tests for Stage 32 Gate C:
Immutable Dataset Snapshot Creation, Cryptographic Replay & Integrity Engine.

Workstream 32.3, 32.4, 32.5, 32.6:
- Manifest precision: 8-decimal financial precision canonicalization & versioning.
- Snapshot creation: transactional consistency, authorization, idempotency, PIT cutoff sealing.
- Snapshot replay: verified deterministic panel reconstruction from frozen payload.
- Immutability under operational mutations: modifying, adding, or deleting operational rows
  cannot silently alter the snapshot replay.
- Anti-tampering: corrupted frozen payloads fail closed on Merkle root mismatch.
- Missing payload: fails closed; silent fallback to current data is strictly rejected.
- Backtesting & Research linkages: atomic binding and reproducibility checks.
- API endpoints: snapshot lifecycle and verification routes.
"""

from datetime import date, datetime, timezone
import json
import uuid

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import hash_password
from app.backtesting.models import BacktestRequest
from app.backtesting.service import execute_backtest, get_backtest_by_id
from app.db.models import (
    BacktestRunModel,
    CorporateActionModel,
    DatasetModel,
    DatasetSnapshotModel,
    PriceBarModel,
    ResearchExperimentModel,
    ResearchExperimentRunModel,
    UserModel,
)
from app.db.session import get_db_session
from app.main import app
from app.market_data.corporate_actions import (
    CorporateActionEvent,
    CorporateActionStatus,
    CorporateActionType,
)
from app.market_data.manifest import (
    build_dataset_manifest,
    compute_price_bars_digest,
)
from app.market_data.snapshot_service import (
    SnapshotIntegrityError,
    SnapshotNotFoundError,
    SnapshotPermissionError,
    SnapshotValidationError,
    create_dataset_snapshot,
    get_snapshot_by_id,
    list_dataset_snapshots,
    resolve_snapshot_price_panel,
    verify_snapshot_integrity,
)
from app.research.service import ResearchService
from tests.conftest import TEST_RESEARCHER_ID


@pytest.fixture
def test_setup():
    """Sets up an isolated test user and dataset with price bars and corporate actions."""
    user_id = TEST_RESEARCHER_ID
    dataset_id = str(uuid.uuid4())

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        if user is None:
            user = UserModel(
                id=user_id,
                email="test.researcher@quantengine.local",
                hashed_password=hash_password("DevTestPass123!"),
                full_name="Default Test Researcher",
                role="researcher",
                is_active=True,
            )
            session.add(user)

        dataset = DatasetModel(
            id=dataset_id,
            user_id=user_id,
            is_shared=False,
            filename="historical_panel.csv",
            source_type="csv_upload",
            content_sha256="abcd1234abcd1234",
            rows_examined=10,
            valid_rows=10,
            rejected_rows=0,
            status="completed",
        )
        session.add(dataset)

        # Add price bars for AAPL and MSFT over 4 trading days
        bars = [
            # AAPL
            PriceBarModel(dataset_id=dataset_id, asset_id="AAPL:US", ticker="AAPL", market="US", currency="USD", date=date(2024, 1, 2), open=180.0, high=182.0, low=179.0, close=181.0, adj_close=181.0, volume=1000000.0),
            PriceBarModel(dataset_id=dataset_id, asset_id="AAPL:US", ticker="AAPL", market="US", currency="USD", date=date(2024, 1, 3), open=181.0, high=183.0, low=180.0, close=182.0, adj_close=182.0, volume=1100000.0),
            PriceBarModel(dataset_id=dataset_id, asset_id="AAPL:US", ticker="AAPL", market="US", currency="USD", date=date(2024, 1, 4), open=182.0, high=185.0, low=181.0, close=184.0, adj_close=184.0, volume=1200000.0),
            PriceBarModel(dataset_id=dataset_id, asset_id="AAPL:US", ticker="AAPL", market="US", currency="USD", date=date(2024, 1, 5), open=184.0, high=186.0, low=183.0, close=185.0, adj_close=185.0, volume=1300000.0),
            # MSFT
            PriceBarModel(dataset_id=dataset_id, asset_id="MSFT:US", ticker="MSFT", market="US", currency="USD", date=date(2024, 1, 2), open=370.0, high=374.0, low=368.0, close=372.0, adj_close=372.0, volume=800000.0),
            PriceBarModel(dataset_id=dataset_id, asset_id="MSFT:US", ticker="MSFT", market="US", currency="USD", date=date(2024, 1, 3), open=372.0, high=375.0, low=370.0, close=373.0, adj_close=373.0, volume=850000.0),
            PriceBarModel(dataset_id=dataset_id, asset_id="MSFT:US", ticker="MSFT", market="US", currency="USD", date=date(2024, 1, 4), open=373.0, high=376.0, low=371.0, close=375.0, adj_close=375.0, volume=900000.0),
            PriceBarModel(dataset_id=dataset_id, asset_id="MSFT:US", ticker="MSFT", market="US", currency="USD", date=date(2024, 1, 5), open=375.0, high=378.0, low=374.0, close=377.0, adj_close=377.0, volume=950000.0),
        ]
        session.add_all(bars)

        # Add corporate action: AAPL stock split 2:1 effective 2024-01-04
        split_event = CorporateActionModel(
            id=f"ca_split_{uuid.uuid4().hex[:8]}",
            dataset_id=dataset_id,
            asset_id="AAPL:US",
            ticker="AAPL",
            market="US",
            event_type="stock_split",
            effective_date=date(2024, 1, 4),
            announcement_date=date(2023, 12, 15),
            value=2.0,
            currency="USD",
            source="SEC_8K",
            status="active",
            is_point_in_time_verified=True,
        )
        session.add(split_event)
        session.commit()

    return {"user_id": user_id, "dataset_id": dataset_id}


# =============================================================================
# 1. Manifest Precision & Schema Versioning Tests
# =============================================================================

def test_manifest_financial_precision_and_sub_penny_sensitivity():
    """
    Workstream 32.3: Validates that 8-decimal float formatting preserves sub-penny prices
    and that sub-penny modifications change the digest.
    """
    rec1 = [
        {"ticker": "PENN", "market": "US", "currency": "USD", "date": "2024-01-02", "close": 0.00012545, "open": 0.00012000, "high": 0.00013000, "low": 0.00011500, "volume": 1000000.0}
    ]
    rec2 = [
        {"ticker": "PENN", "market": "US", "currency": "USD", "date": "2024-01-02", "close": 0.00012546, "open": 0.00012000, "high": 0.00013000, "low": 0.00011500, "volume": 1000000.0}
    ]

    # In v1.1, changing the 8th decimal place MUST alter the digest
    d1, _, _ = compute_price_bars_digest(rec1, manifest_version="1.1")
    d2, _, _ = compute_price_bars_digest(rec2, manifest_version="1.1")
    assert d1 != d2, "Manifest version 1.1 must detect sub-penny price differences at 8 decimal places"

    # Schema versioning
    m1 = build_dataset_manifest("ds1", rec1, manifest_version="1.1")
    m2 = build_dataset_manifest("ds1", rec1, manifest_version="1.0")
    assert m1.manifest_version == "1.1"
    assert m2.manifest_version == "1.0"
    assert m1.manifest_sha256 != m2.manifest_sha256, "Manifest digest must be version-tagged"


# =============================================================================
# 2. Snapshot Creation Tests
# =============================================================================

def test_snapshot_creation_success(test_setup):
    """
    Workstream 32.4: Validates that create_dataset_snapshot captures frozen data,
    computes canonical manifest, and stores frozen_payload_json.
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snapshot = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="baseline_2024",
            description="Initial verified research snapshot",
            snapshot_type="manual",
            strict_pit=True,
        )
        session.commit()

        assert snapshot.id is not None
        assert snapshot.dataset_id == dataset_id
        assert snapshot.tag == "baseline_2024"
        assert snapshot.is_frozen is True
        assert snapshot.total_bars_count == 8
        assert snapshot.total_actions_count == 1
        assert snapshot.point_in_time_status == "verified_point_in_time"
        assert len(snapshot.manifest_sha256) == 64
        assert snapshot.frozen_payload_json is not None

        # Verify manifest deserialization
        manifest_data = snapshot.get_manifest()
        assert manifest_data["dataset_id"] == dataset_id
        assert "AAPL:US" in manifest_data["assets"]
        assert "MSFT:US" in manifest_data["assets"]


def test_snapshot_creation_unauthorized_fails(test_setup):
    """
    Validates that creating a snapshot on a private dataset by an unauthorized user is rejected.
    """
    dataset_id = test_setup["dataset_id"]
    unauth_user_id = str(uuid.uuid4())

    with get_db_session() as session:
        unauth_user = UserModel(
            id=unauth_user_id,
            email=f"unauth_{unauth_user_id[:8]}@quantengine.local",
            hashed_password=hash_password("DevPass123!"),
            full_name="Unauthorized User",
            role="researcher",
            is_active=True,
        )
        session.add(unauth_user)
        session.commit()

    with get_db_session() as session:
        user = session.get(UserModel, unauth_user_id)
        with pytest.raises(Exception):  # HTTPException 403 or SnapshotPermissionError
            create_dataset_snapshot(
                dataset_id=dataset_id,
                user=user,
                session=session,
                tag="illegal_snapshot",
            )


def test_snapshot_creation_retries_idempotent(test_setup):
    """
    Validates that re-running snapshot creation with the same tag and unchanged dataset
    returns the existing snapshot (idempotent retry).
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snap1 = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="idempotent_test",
        )
        session.commit()
        snap1_id = snap1.id
        snap1_hash = snap1.manifest_sha256

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snap2 = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="idempotent_test",
        )
        assert snap1_id == snap2.id
        assert snap1_hash == snap2.manifest_sha256


# =============================================================================
# 3. Snapshot Replay & Immutability Verification Tests
# =============================================================================

def test_snapshot_replay_success(test_setup):
    """
    Workstream 32.5: Validates exact price panel resolution from frozen payload.
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snapshot = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="replay_test_tag",
        )
        session.commit()
        snapshot_id = snapshot.id

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        clean_df, assets, currency, periods, provenance = resolve_snapshot_price_panel(
            snapshot_id=snapshot_id,
            user=user,
            session=session,
            requested_assets=["AAPL", "MSFT"],
            adjustment_type="total",
        )

        assert currency == "USD"
        assert periods == 252
        assert len(assets) == 2
        assert len(clean_df) == 4
        assert "AAPL:US" in clean_df.columns
        assert "MSFT:US" in clean_df.columns

        # Verify provenance attached
        assert provenance["snapshot_id"] == snapshot_id
        assert provenance["verified_replay"] is True
        assert clean_df.attrs["snapshot_provenance"]["verified_replay"] is True


def test_immutability_under_operational_dataset_mutation(test_setup):
    """
    CRITICAL PROOF OF IMMUTABILITY:
    1. Create a snapshot.
    2. Replay panel -> panel_1.
    3. Mutate operational price_bars table (modify prices, add rows).
    4. Mutate corporate_actions table (add unverified new corporate action).
    5. Replay snapshot again -> panel_2.
    6. PROVE panel_1 and panel_2 are strictly identical (zero drift).
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snapshot = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="frozen_lock_test",
        )
        session.commit()
        snapshot_id = snapshot.id

    # Replay initial panel
    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        panel_initial, _, _, _, prov1 = resolve_snapshot_price_panel(
            snapshot_id=snapshot_id,
            user=user,
            session=session,
            adjustment_type="total",
        )

    # NOW AGGRESSIVELY MUTATE OPERATIONAL TABLES!
    with get_db_session() as session:
        # 1. Modify existing close price
        bar = session.scalars(
            select(PriceBarModel).where(
                PriceBarModel.dataset_id == dataset_id,
                PriceBarModel.ticker == "AAPL",
                PriceBarModel.date == date(2024, 1, 2),
            )
        ).first()
        assert bar is not None
        bar.close = 9999.99  # Corrupt operational table

        # 2. Insert new row that wasn't in snapshot
        new_bar = PriceBarModel(
            dataset_id=dataset_id,
            asset_id="AAPL:US",
            ticker="AAPL",
            market="US",
            currency="USD",
            date=date(2024, 1, 8),
            open=200.0,
            high=205.0,
            low=199.0,
            close=202.0,
            adj_close=202.0,
            volume=5000000.0,
        )
        session.add(new_bar)

        # 3. Add brand new corporate action to operational table
        new_ca = CorporateActionModel(
            id=f"ca_mutated_{uuid.uuid4().hex[:8]}",
            dataset_id=dataset_id,
            asset_id="MSFT:US",
            ticker="MSFT",
            market="US",
            event_type="stock_split",
            effective_date=date(2024, 1, 3),
            announcement_date=date(2024, 1, 1),
            value=10.0,
            currency="USD",
            source="FAKE_MUTATION",
            status="active",
        )
        session.add(new_ca)
        session.commit()

    # Replay snapshot after operational table mutations
    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        panel_after_mutation, _, _, _, prov2 = resolve_snapshot_price_panel(
            snapshot_id=snapshot_id,
            user=user,
            session=session,
            adjustment_type="total",
        )

    # MATHEMATICAL PROOF: Snapshot is 100% immune to operational database mutations!
    pd.testing.assert_frame_equal(panel_initial, panel_after_mutation)
    assert prov1["manifest_sha256"] == prov2["manifest_sha256"]
    # AAPL 2024-01-02 close was adjusted by 2:1 split (181.0 / 2 = 90.5), NOT 9999.99
    assert np.isclose(panel_after_mutation.loc["2024-01-02", "AAPL:US"], 90.5)


def test_corrupted_frozen_payload_fails_closed(test_setup):
    """
    Validates that tampering with the frozen payload fails cryptographic Merkle verification.
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snapshot = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="tamper_test",
        )
        session.commit()
        snapshot_id = snapshot.id

    # Tamper with the frozen payload directly in the snapshot model
    with get_db_session() as session:
        snap = session.get(DatasetSnapshotModel, snapshot_id)
        payload = json.loads(snap.frozen_payload_json)
        # Corrupt 1 price
        payload["price_bars"][0]["close"] = 999.0
        snap.frozen_payload_json = json.dumps(payload)
        session.commit()

    # Replay must FAIL CLOSED
    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        with pytest.raises(SnapshotIntegrityError) as exc_info:
            resolve_snapshot_price_panel(
                snapshot_id=snapshot_id,
                user=user,
                session=session,
            )
        assert "Cryptographic integrity verification failed" in str(exc_info.value)


def test_missing_frozen_payload_fails_closed_no_fallback(test_setup):
    """
    Validates that a snapshot missing frozen_payload_json fails closed immediately,
    and never silently queries current mutable tables.
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snapshot = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="missing_payload_test",
        )
        session.commit()
        snapshot_id = snapshot.id

    # Set frozen_payload_json to None
    with get_db_session() as session:
        snap = session.get(DatasetSnapshotModel, snapshot_id)
        snap.frozen_payload_json = None
        session.commit()

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        with pytest.raises(SnapshotIntegrityError) as exc_info:
            resolve_snapshot_price_panel(
                snapshot_id=snapshot_id,
                user=user,
                session=session,
            )
        assert "lacks frozen payload" in str(exc_info.value)


# =============================================================================
# 4. Backtest & Research Experiment Linkage Tests
# =============================================================================

def test_backtest_with_explicit_snapshot_id(test_setup):
    """
    Workstream 32.6: Validates that executing a backtest with snapshot_id resolves
    via resolve_snapshot_price_panel and binds snapshot_id to BacktestRunModel.
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snapshot = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="bt_link_snap",
        )
        session.commit()
        snapshot_id = snapshot.id

    req = BacktestRequest(
        dataset_id=dataset_id,
        snapshot_id=snapshot_id,
        name="Snapshot Bound Backtest",
        strategy_type="equal_weight",
        assets=["AAPL", "MSFT"],
        initial_capital=100000.0,
    )

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        resp = execute_backtest(req, user, session)
        assert resp.snapshot_id == snapshot_id
        assert resp.snapshot_provenance is not None
        assert resp.snapshot_provenance["verified_replay"] is True

        # Verify database linkage
        run_record = session.get(BacktestRunModel, resp.id)
        assert run_record.snapshot_id == snapshot_id
        assert run_record.snapshot.tag == "bt_link_snap"


def test_backtest_auto_snapshot(test_setup):
    """
    Workstream 32.6: Validates that auto_snapshot=True creates a frozen snapshot
    prior to simulation and binds it atomically to the backtest run.
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    req = BacktestRequest(
        dataset_id=dataset_id,
        auto_snapshot=True,
        name="Auto-Snapshot Backtest",
        strategy_type="equal_weight",
        assets=["AAPL", "MSFT"],
        initial_capital=100000.0,
    )

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        resp = execute_backtest(req, user, session)
        assert resp.snapshot_id is not None
        assert resp.snapshot_provenance is not None

        run_record = session.get(BacktestRunModel, resp.id)
        assert run_record.snapshot_id == resp.snapshot_id
        assert run_record.snapshot.snapshot_type == "auto_backtest"


def test_research_experiment_run_with_snapshot_linkage(test_setup):
    """
    Workstream 32.6: Validates research experiment run linkage to an immutable snapshot
    and verifies that check_run_reproducibility certifies the run via snapshot.
    """
    user_id = test_setup["user_id"]
    dataset_id = test_setup["dataset_id"]

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        snapshot = create_dataset_snapshot(
            dataset_id=dataset_id,
            user=user,
            session=session,
            tag="exp_snap",
        )
        session.commit()
        snapshot_id = snapshot.id

    # Create research experiment
    exp_cfg = {
        "strategy_type": "equal_weight",
        "dataset_id": dataset_id,
        "assets": ["AAPL", "MSFT"],
        "initial_capital": 100000.0,
        "snapshot_id": snapshot_id,
    }

    with get_db_session() as session:
        exp = ResearchExperimentModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            dataset_id=dataset_id,
            name="Snapshot Verified Experiment",
            strategy_type="equal_weight",
            config_json=json.dumps(exp_cfg),
            config_fingerprint="fp123456",
        )
        session.add(exp)
        session.commit()
        exp_id = exp.id

    with get_db_session() as session:
        user = session.get(UserModel, user_id)
        run_resp = ResearchService.execute_experiment_run(exp_id, user, session)
        assert run_resp.snapshot_id == snapshot_id
        assert run_resp.is_reproducible is True
        assert any("Bound to immutable dataset snapshot" in note for note in run_resp.reproducibility_notes)


# =============================================================================
# 5. Snapshot API Route Tests
# =============================================================================

def test_snapshot_api_lifecycle(test_setup):
    """
    Tests REST API endpoints for snapshot creation, listing, details, and verification.
    """
    client = TestClient(app)
    dataset_id = test_setup["dataset_id"]

    # 1. Create snapshot via POST /api/v1/datasets/{dataset_id}/snapshots
    create_payload = {
        "tag": "api_test_v1",
        "description": "API created snapshot",
        "strict_pit": True,
    }
    create_res = client.post(
        f"/api/v1/datasets/{dataset_id}/snapshots",
        json=create_payload,
    )
    assert create_res.status_code == 201, create_res.text
    snap_data = create_res.json()
    snapshot_id = snap_data["id"]
    assert snap_data["tag"] == "api_test_v1"
    assert snap_data["is_frozen"] is True

    # 2. List snapshots via GET /api/v1/datasets/{dataset_id}/snapshots
    list_res = client.get(f"/api/v1/datasets/{dataset_id}/snapshots")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(s["id"] == snapshot_id for s in items)

    # 3. Get snapshot details via GET /api/v1/datasets/snapshots/{snapshot_id}
    get_res = client.get(f"/api/v1/datasets/snapshots/{snapshot_id}")
    assert get_res.status_code == 200
    assert get_res.json()["manifest_sha256"] == snap_data["manifest_sha256"]

    # 4. Verify integrity via GET /api/v1/datasets/snapshots/{snapshot_id}/verify
    verify_res = client.get(f"/api/v1/datasets/snapshots/{snapshot_id}/verify")
    assert verify_res.status_code == 200
    assert verify_res.json()["is_verified"] is True


def test_snapshot_api_malformed_payload_returns_409(test_setup):
    """
    Workstream 32.B (Gate F remediation):
    Malformed or corrupt JSON in frozen_payload_json must fail closed with HTTP 409 (Conflict)
    rather than an unhandled 500 server error.
    """
    client = TestClient(app)
    dataset_id = test_setup["dataset_id"]

    # 1. Create a snapshot
    create_res = client.post(
        f"/api/v1/datasets/{dataset_id}/snapshots",
        json={"tag": "malformed_test_snap", "description": "Testing malformed payload"},
    )
    assert create_res.status_code == 201
    snapshot_id = create_res.json()["id"]

    # 2. Corrupt payload JSON in the database directly
    with get_db_session() as session:
        snap = session.get(DatasetSnapshotModel, snapshot_id)
        snap.frozen_payload_json = "{ INVALID_JSON: corrupt }}}"
        session.commit()

    # 3. Call verify route - must return 409 Conflict with informative message
    verify_res = client.get(f"/api/v1/datasets/snapshots/{snapshot_id}/verify")
    assert verify_res.status_code == 409
    assert "Failed to deserialize frozen payload" in verify_res.json()["detail"]


def test_snapshot_api_empty_bars_payload_returns_409(test_setup):
    """
    Workstream 32.B (Gate F remediation):
    A frozen payload with empty bars must fail closed with HTTP 409.
    """
    client = TestClient(app)
    dataset_id = test_setup["dataset_id"]

    create_res = client.post(
        f"/api/v1/datasets/{dataset_id}/snapshots",
        json={"tag": "empty_bars_snap", "description": "Testing empty bars payload"},
    )
    assert create_res.status_code == 201
    snapshot_id = create_res.json()["id"]

    with get_db_session() as session:
        snap = session.get(DatasetSnapshotModel, snapshot_id)
        snap.frozen_payload_json = json.dumps({"price_bars": [], "corporate_actions": []})
        session.commit()

    verify_res = client.get(f"/api/v1/datasets/snapshots/{snapshot_id}/verify")
    assert verify_res.status_code == 409
    assert "contains no price bars" in verify_res.json()["detail"]


def test_snapshot_v1_2_currency_tampering_fails_verification(test_setup):
    """
    Workstream 32.A (Gate F remediation):
    Under manifest_version '1.2', mutating currency inside the frozen payload
    causes cryptographic verification to fail closed with SnapshotIntegrityError and HTTP 409.
    """
    client = TestClient(app)
    dataset_id = test_setup["dataset_id"]

    create_res = client.post(
        f"/api/v1/datasets/{dataset_id}/snapshots",
        json={"tag": "currency_tamper_test", "description": "Testing currency tampering"},
    )
    assert create_res.status_code == 201
    snapshot_id = create_res.json()["id"]

    # Mutate currency in frozen payload JSON from USD to EUR
    with get_db_session() as session:
        snap = session.get(DatasetSnapshotModel, snapshot_id)
        payload = json.loads(snap.frozen_payload_json)
        assert payload["price_bars"][0]["currency"] == "USD"
        payload["price_bars"][0]["currency"] = "EUR"
        snap.frozen_payload_json = json.dumps(payload)
        session.commit()

    # Direct service call raises SnapshotIntegrityError
    with get_db_session() as session:
        with pytest.raises(SnapshotIntegrityError) as exc_info:
            verify_snapshot_integrity(snapshot_id, session)
        assert "Digest mismatch in snapshot" in str(exc_info.value)

    # API verify route returns HTTP 409
    verify_res = client.get(f"/api/v1/datasets/snapshots/{snapshot_id}/verify")
    assert verify_res.status_code == 409
    assert "Digest mismatch in snapshot" in verify_res.json()["detail"]

