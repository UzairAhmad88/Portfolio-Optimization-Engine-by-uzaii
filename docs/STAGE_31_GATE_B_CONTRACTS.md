# Stage 31 — Gate B: Calendar, Source, and Corporate Action Event Contracts
**Quant Portfolio Optimization Engine | US Equities & Pakistan Stock Exchange (PSX)**

## 1. Executive Summary
- **Gate Status:** PASS
- **Approved Scope:** Exchange trading calendars and canonical corporate actions event model for US Equities (NYSE/NASDAQ) and PSX.
- **Completed Workstreams:**
  - Workstream 31.1: Exchange Calendars and Session Integrity
  - Workstream 31.2: Canonical Corporate-Action Event Model & Provider Adapters

---

## 2. Workstream 31.1: Exchange Calendars Implementation (`calendars.py`)
1. **Explicit Exchange Identity & Versioning:**
   - US Equities: `calendar_id="US_EQUITY"`, `version="US-NYSE-2026.1"`, Timezone: `America/New_York`.
   - PSX Equities: `calendar_id="PSX_EQUITY"`, `version="PSX-KHI-2026.1"`, Timezone: `Asia/Karachi`.
2. **Session & Holiday Integrity:**
   - US Calendar incorporates all 10 statutory exchange holidays (New Year's, MLK Day, Presidents' Day, Good Friday [Easter Computus algorithm], Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas), weekend shift rules (Saturday -> Friday, Sunday -> Monday), and documented historical exceptional closures (9/11 attacks Sept 11-14 2001, Hurricane Sandy Oct 29-30 2012, President George H.W. Bush funeral Dec 5 2018).
   - PSX Calendar incorporates fixed national holidays (Kashmir Day Feb 5, Pakistan Day Mar 23, Labour Day May 1, Independence Day Aug 14, Iqbal Day Nov 9, Quaid-e-Azam Day Dec 25, Bank Holidays Jan 1 and July 1) and authoritative gazetted Islamic lunar holiday tables (Eid-ul-Fitr, Eid-ul-Adha, Ashura, Eid Milad-un-Nabi) across 2020–2026+.
3. **Missing Session Anomaly Detection:**
   - `detect_missing_sessions(observed_dates, start_date, end_date)` compares observed price bar dates against open trading sessions.
   - Genuine missing days generate `DQ_MISSING_SESSION` errors.
   - Legitimate holidays and weekends are **never** flagged as missing observations.
4. **Cross-Market Session Alignment:**
   - `align_cross_market_sessions` supports `intersection` (strictly synchronized observations) and `union` (with structured holiday asymmetry warnings).

---

## 3. Workstream 31.2: Corporate Actions Model (`corporate_actions.py`, `adapters.py`)
1. **Canonical Event Structure (`CorporateActionEvent`):**
   - Supported event types: `stock_split`, `reverse_split`, `cash_dividend`, `symbol_change`, and `complex_unsupported` (mergers, spin-offs, rights offerings, capital distributions).
   - Separation of ticker symbol from stable internal `asset_id`.
   - Explicit temporal semantics: `effective_date`, `announcement_date`, `ex_date`, `record_date`, `payment_date`.
2. **Deterministic Ledger & Revision Control (`CorporateActionLedger`):**
   - Deduplication: Identical provider events are deduplicated idempotently.
   - Supersession: Confirmed corrections/revisions supersede prior active records with full audit trail (`status="superseded"`).
   - Symbol Mapping (`SymbolMappingRegistry`): Tracks symbol renames across time (e.g., `FB` -> `META`), resolving to the same underlying economic asset.
3. **Point-in-Time Filtering:**
   - `strict_pit=True`: Only events with `announcement_date <= as_of_date` are eligible. Lookahead leakage is prevented.
   - Unverified events lacking an announcement timestamp fail closed in strict mode.
4. **Provider-Neutral Adapter Interface (`adapters.py`):**
   - `MarketDataProviderAdapter` abstract base class with declared `ProviderCapabilities`.
   - `CSVUploadAdapter` explicitly declares capability limitations (e.g., cannot guarantee PIT announcement timestamps unless provided in upload).

---

## 4. Test Verification
- `backend/tests/test_exchange_calendars.py`: Ordinary sessions, holidays, exceptional closures, missing session detection, cross-market alignment, factory instantiation.
- `backend/tests/test_corporate_actions.py`: Validation, deduplication, revision supersession, symbol mapping across renames, strict point-in-time negative leakage tests.
