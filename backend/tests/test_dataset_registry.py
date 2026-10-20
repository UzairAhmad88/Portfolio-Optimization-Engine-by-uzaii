import concurrent.futures
from datetime import date

import pytest

from app.market_data.service import (
    DatasetNotFoundError,
    clear_dataset_registry,
    get_dataset_metadata,
    get_dataset_registry_capacity,
    get_dataset_registry_size,
    query_dataset,
    register_csv_dataset,
    set_dataset_registry_capacity,
)

SAMPLE_CSV_A = b"date,ticker,market,close,currency\n2025-01-02,AAPL,US,100,USD\n"

SAMPLE_CSV_B = b"date,ticker,market,close,currency\n2025-01-02,MSFT,US,200,USD\n"

SAMPLE_CSV_C = b"date,ticker,market,close,currency\n2025-01-02,GOOG,US,300,USD\n"


@pytest.fixture(autouse=True)
def clean_registry():
    clear_dataset_registry()
    set_dataset_registry_capacity(30)
    yield
    clear_dataset_registry()
    set_dataset_registry_capacity(30)


def test_registry_default_capacity():
    assert get_dataset_registry_capacity() == 30
    assert get_dataset_registry_size() == 0


def test_registry_capacity_limit_and_lru_eviction():
    set_dataset_registry_capacity(2)
    assert get_dataset_registry_capacity() == 2

    meta1 = register_csv_dataset(SAMPLE_CSV_A, "a.csv")
    id1 = meta1["dataset_id"]
    assert get_dataset_registry_size() == 1

    meta2 = register_csv_dataset(SAMPLE_CSV_B, "b.csv")
    id2 = meta2["dataset_id"]
    assert get_dataset_registry_size() == 2

    # Registering third dataset must evict oldest (id1)
    meta3 = register_csv_dataset(SAMPLE_CSV_C, "c.csv")
    id3 = meta3["dataset_id"]
    assert get_dataset_registry_size() == 2

    # id1 should now be evicted
    with pytest.raises(DatasetNotFoundError):
        get_dataset_metadata(id1)

    # id2 and id3 must still exist
    assert get_dataset_metadata(id2)["filename"] == "b.csv"
    assert get_dataset_metadata(id3)["filename"] == "c.csv"


def test_registry_access_refreshes_recency():
    set_dataset_registry_capacity(2)

    meta1 = register_csv_dataset(SAMPLE_CSV_A, "a.csv")
    id1 = meta1["dataset_id"]

    meta2 = register_csv_dataset(SAMPLE_CSV_B, "b.csv")
    id2 = meta2["dataset_id"]

    # Accessing id1 refreshes its recency (making id2 the least recently used)
    get_dataset_metadata(id1)

    # Adding third dataset must now evict id2, NOT id1!
    meta3 = register_csv_dataset(SAMPLE_CSV_C, "c.csv")
    id3 = meta3["dataset_id"]

    # id2 was evicted
    with pytest.raises(DatasetNotFoundError):
        get_dataset_metadata(id2)

    # id1 and id3 are retained
    assert get_dataset_metadata(id1)["filename"] == "a.csv"
    assert get_dataset_metadata(id3)["filename"] == "c.csv"


def test_query_dataset_refreshes_recency():
    set_dataset_registry_capacity(2)

    meta1 = register_csv_dataset(SAMPLE_CSV_A, "a.csv")
    id1 = meta1["dataset_id"]

    meta2 = register_csv_dataset(SAMPLE_CSV_B, "b.csv")
    id2 = meta2["dataset_id"]

    # Querying id1 refreshes its recency
    res = query_dataset(id1, start_date=date(2025, 1, 1), end_date=date(2025, 1, 5))
    assert res["row_count"] == 1

    # Adding third dataset evicts id2
    meta3 = register_csv_dataset(SAMPLE_CSV_C, "c.csv")
    id3 = meta3["dataset_id"]

    with pytest.raises(DatasetNotFoundError):
        get_dataset_metadata(id2)

    assert get_dataset_metadata(id1)["dataset_id"] == id1
    assert get_dataset_metadata(id3)["dataset_id"] == id3


def test_unknown_dataset_id_raises_not_found():
    with pytest.raises(DatasetNotFoundError, match="was not found"):
        get_dataset_metadata("non-existent-uuid")

    with pytest.raises(DatasetNotFoundError, match="was not found"):
        query_dataset(
            "non-existent-uuid",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )


def test_concurrent_registrations_and_reads():
    set_dataset_registry_capacity(50)
    num_threads = 10
    datasets_per_thread = 5

    def worker(worker_id: int):
        created_ids = []
        for i in range(datasets_per_thread):
            csv_content = f"date,ticker,market,close,currency\n2025-01-02,T{worker_id}_{i},US,100,USD\n".encode()
            meta = register_csv_dataset(csv_content, f"worker_{worker_id}_{i}.csv")
            created_ids.append(meta["dataset_id"])
        # Perform concurrent reads
        for did in created_ids:
            fetched = get_dataset_metadata(did)
            assert fetched["dataset_id"] == did
        return created_ids

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, w) for w in range(num_threads)]
        all_ids = []
        for f in concurrent.futures.as_completed(futures):
            all_ids.extend(f.result())

    assert len(all_ids) == num_threads * datasets_per_thread
    assert get_dataset_registry_size() == 50
