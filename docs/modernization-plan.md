# CatTrack Structural Modernization Plan

Phased cleanup of this long-lived (Django 1.9 → 5.2) codebase. Each phase is a
self-contained PR. Phases are behaviour-preserving unless noted: no API response
shapes change, and the OpenAPI schema diff should be empty.

## Phase 1 — model field & idiom hygiene ✅ (#78)

Low-risk model hygiene, no API behaviour change.

- `TextField(max_length=...)` → `CharField` for `Account.name`, `Category.name`
- Explicit `on_delete=` keyword on legacy positional `ForeignKey`s
- `related_name="transactions"` on `Transaction.account`
- Hot-column indexes via `Meta.indexes`: `Transaction.when`, `Bill.due_date`
- Drop redundant `default=None` on nullable `BudgetEntry.name`
- `verbose_name_plural` on `CategorisorModel`, `UserSettings`
- Fix missing `return` in `BudgetEntry.pretty_valid()` (>27-day branch)
- Narrow bare `except:` in `Account.load_transactions` to `Transaction.DoesNotExist`

## Phase 2 — eliminate N+1 query patterns ✅ (#80)

Behaviour-preserving query optimisations.

- `Transaction.suggest_category(clf, category_map=None)` builds a `{name: id}` map
  once per call instead of one `Category.objects.get()` per predicted label.
  Unknown labels are now skipped rather than raising `DoesNotExist`.
- Loop callers (`AccountViewSet.load`, `CategorisorViewSet.validate`) build the map
  once and pass it in.
- `select_related('category')` on `TransactionViewSet`.
- `prefetch_related` on `RecurringPaymentViewSet` and `BillViewSet`;
  `Bill.is_paid` sums over the related manager so the prefetch cache is reused.
- Adds `test_query_perf.py` regression tests.

## Phase 3 — serializer consolidation ✅ (#84)

- All serializers live under `ctrack/api/serializers/`, one module per domain.
- Stray top-level `data_serializer.py` / `series_serializer.py` folded into
  `serializers/common.py`.
- File-upload validation (size ceiling + extension allow-list) on
  `LoadDataSerializer`.

## Phase 4 — service layer extraction ✅ (this PR)

Introduce `ctrack/services/` and move business logic out of fat models and views.
Views become thin (parse → service → serialize); models keep data plus trivial
delegating accessors. Behaviour-preserving; 123 tests green.

- `import_service` — `Account.load_transactions` orchestration and
  `RecurringPayment.add_bill_from_file`.
- `categorisation_service` — wraps `ctrack.categories`
  (`suggest_categories` / `get_clf_model` / `load_categoriser`).
- `progress_service` — the ~300-line `ProgressView` computation
  (`resolve_period`, `compute_progress`, `_spend_by_category[_group]`).
- `reporting_service` — pandas-heavy account balance and bill-series reporting.

## Remaining / deferred work

- **Pagination (`PAGE_SIZE`)** — the global DRF default has no `PAGE_SIZE`, so most
  list endpoints are unpaginated. Setting it changes the response envelope and
  needs a frontend-consumer audit. Proposed as its own PR (not behaviour-preserving).
- **`suggest_category` N+1 in the legacy disk path** — largely addressed in Phase 2
  via `category_map`; confirm no remaining callers rebuild the map per row.
