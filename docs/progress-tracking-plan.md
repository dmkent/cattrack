# Progress Tracking APIs - Implementation Plan

## Context

Build APIs to drive a progress tracking view in the React frontend. The view lets users choose a period (week, month, quarter) and see spending by category/category group — both actual spend so far and expected remaining spend based on historical data.

Currently, RecurringPayment/Bill objects are created manually and are likely sparse. To make "expected spend" predictions useful, we first auto-detect recurring transactions from history. This splits into two phases:

- **Phase 1**: Auto-detect recurring transactions using clustering (populate RecurringPayment/Bill data)
- **Phase 2**: Progress tracking API (actual spend + expected remaining + budgets + recurring bills)

**First step of implementation**: Create `docs/` directory and save this plan to `docs/progress-tracking-plan.md` in the repo, commit it, then proceed with Phase 1.

---

## Phase 1: Recurring Transaction Detection

### Task 1A: Model Change + Migration

**File:** `ctrack/models.py` — add `category` FK to `RecurringPayment` (line ~312, after `is_income`):

```python
category = models.ForeignKey('Category', null=True, blank=True, on_delete=models.SET_NULL)
```

Then run `python manage.py makemigrations` and `python manage.py migrate`.

**Why:** Lets recurring bills be mapped to spending categories for the Phase 2 progress view. The `create_from_detection` endpoint can auto-set this from the most common category in the detected cluster.

**Existing model reference** (`ctrack/models.py:309-312`):
```python
class RecurringPayment(models.Model):
    """A recurring bill series."""
    name = models.CharField(max_length=100)
    is_income = models.BooleanField(default=False)
```

**Also update the serializer** in `ctrack/api/recurring_payment.py:23-28` to include `category`:
```python
class RecurringPaymentSerializer(serializers.ModelSerializer):
    bills = BillSerializer(many=True, read_only=True)
    class Meta:
        model = RecurringPayment
        fields = ('url', 'id', 'name', 'is_income', 'bills', 'next_due_date', 'category')
```

---

### Task 1B: Core Detection Algorithm

**New file:** `ctrack/recurring_detection.py`

Standalone class `RecurringTransactionDetector`, following the pattern of `ctrack/categories.py` (ML logic separate from API layer).

**Dependencies available** (from `requirements.txt`): scikit-learn 1.6.1, numpy 1.26.4, pandas 2.2.3.

**Algorithm:**

1. **TF-IDF vectorization** of transaction descriptions using `sklearn.feature_extraction.text.TfidfVectorizer`:
   ```python
   TfidfVectorizer(lowercase=True, token_pattern=r'(?u)\b\w+\b', min_df=2, max_df=0.95)
   ```
   This combines CountVectorizer + TfidfTransformer (used separately in `ctrack/categories.py:101-102`) into one step.

2. **DBSCAN clustering** on TF-IDF vectors with cosine metric:
   ```python
   from sklearn.cluster import DBSCAN
   DBSCAN(eps=similarity_threshold, min_samples=min_cluster_size, metric='cosine')
   ```
   - Default `eps=0.4` → descriptions need ≥0.6 cosine similarity to cluster
   - Default `min_samples=3` → at least 3 transactions to form a group
   - DBSCAN labels noise as -1 (non-recurring transactions)
   - **Note:** DBSCAN with `metric='cosine'` may not accept sparse matrices directly. If so, convert with `.toarray()` — feasible for personal finance data (5k-20k transactions).

3. **Regularity analysis** per cluster:
   - Sort transactions by date, compute inter-transaction intervals in days
   - Coefficient of variation (CV = std/mean) of intervals
   - Filter: keep only clusters with `interval_cv < interval_cv_threshold` (default 0.35)
   - Classify frequency from mean interval:
     - 5-9 days → "weekly"
     - 12-18 days → "fortnightly"
     - 25-35 days → "monthly"
     - 55-100 days → "quarterly"
     - 160-200 days → "semi_annual"
     - 340-400 days → "annual"
     - Other → "irregular"

4. **Amount pattern analysis** per cluster:
   - Compute CV of absolute amounts
   - CV < 0.05 → "fixed" (subscription)
   - CV < 0.3 → "variable_low" (utility bill)
   - Else → "variable_high" (groceries)

5. **Representative description**: most common description in the cluster (`collections.Counter`).

6. **Category inference**: most common category among categorized transactions in the cluster.

**Class interface:**
```python
class RecurringTransactionDetector:
    def __init__(self, min_cluster_size=3, interval_cv_threshold=0.35, similarity_threshold=0.4):
        ...

    def detect(self, transactions_qs) -> list[dict]:
        """Takes a Transaction queryset, returns detected groups."""
        ...
```

**Return format** per group:
```python
{
    "cluster_id": int,
    "description_pattern": str,           # most common description
    "sample_descriptions": list[str],     # up to 5 unique descriptions
    "frequency": str,                     # "weekly"|"monthly"|"quarterly"|etc
    "mean_interval_days": float,
    "interval_cv": float,
    "regularity_score": float,            # max(0, 1.0 - interval_cv)
    "amount_mean": float,
    "amount_std": float,
    "amount_type": str,                   # "fixed"|"variable_low"|"variable_high"
    "is_income": bool,                    # True if mean amount > 0
    "transaction_count": int,
    "transaction_ids": list[int],
    "first_date": date,
    "last_date": date,
    "category": int | None,              # most common category id
    "category_name": str | None,
}
```

---

### Task 1C: Serializers

**New file:** `ctrack/api/serializers/recurring_detection.py`

Follow the pattern in `ctrack/api/serializers/categorisor.py` (custom `serializers.Serializer` classes, not ModelSerializer).

```python
class DetectRecurringRequestSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    min_cluster_size = serializers.IntegerField(default=3, min_value=2, max_value=20)
    interval_cv_threshold = serializers.FloatField(default=0.35, min_value=0.1, max_value=1.0)
    similarity_threshold = serializers.FloatField(default=0.4, min_value=0.1, max_value=0.9)
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), required=False
    )

class DetectedGroupSerializer(serializers.Serializer):
    cluster_id = serializers.IntegerField()
    description_pattern = serializers.CharField()
    sample_descriptions = serializers.ListField(child=serializers.CharField())
    frequency = serializers.CharField()
    mean_interval_days = serializers.FloatField()
    interval_cv = serializers.FloatField()
    regularity_score = serializers.FloatField()
    amount_mean = serializers.FloatField()
    amount_std = serializers.FloatField()
    amount_type = serializers.CharField()
    is_income = serializers.BooleanField()
    transaction_count = serializers.IntegerField()
    transaction_ids = serializers.ListField(child=serializers.IntegerField())
    first_date = serializers.DateField()
    last_date = serializers.DateField()
    category = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)

class DetectRecurringResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    total_transactions = serializers.IntegerField()
    groups_found = serializers.IntegerField()
    groups = DetectedGroupSerializer(many=True)

class CreateFromDetectionItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    transaction_ids = serializers.ListField(child=serializers.IntegerField())
    is_income = serializers.BooleanField(default=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )

class CreateFromDetectionSerializer(serializers.Serializer):
    groups = CreateFromDetectionItemSerializer(many=True)
```

---

### Task 1D: API Endpoints

**Modify:** `ctrack/api/recurring_payment.py` — add two `@decorators.action` methods to `RecurringPaymentViewSet`.

No changes to `ctrack/api/__init__.py` needed — `RecurringPaymentViewSet` is already registered at `payments`, so new actions auto-route to `/api/payments/detect_recurring/` and `/api/payments/create_from_detection/`.

**Endpoint 1: `POST /api/payments/detect_recurring/`**

```python
@decorators.action(detail=False, methods=["post"])
def detect_recurring(self, request):
    serializer = DetectRecurringRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    from_date = serializer.validated_data['from_date']
    to_date = serializer.validated_data['to_date']
    
    # Build queryset
    qs = Transaction.objects.filter(
        when__gte=from_date, when__lte=to_date,
        is_split=False, description__isnull=False
    ).exclude(description='')
    
    if 'account' in serializer.validated_data:
        qs = qs.filter(account=serializer.validated_data['account'])
    
    if qs.count() < 20:
        return response.Response(
            {"status": "error", "detail": "Need at least 20 transactions with descriptions."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    detector = RecurringTransactionDetector(
        min_cluster_size=serializer.validated_data['min_cluster_size'],
        interval_cv_threshold=serializer.validated_data['interval_cv_threshold'],
        similarity_threshold=serializer.validated_data['similarity_threshold'],
    )
    groups = detector.detect(qs)
    
    result = {
        "status": "ok",
        "total_transactions": qs.count(),
        "groups_found": len(groups),
        "groups": groups,
    }
    return response.Response(DetectRecurringResponseSerializer(result).data)
```

**Endpoint 2: `POST /api/payments/create_from_detection/`**

Follow the preview-then-apply pattern from `ctrack/api/categorisor.py:376-388` (`apply_recategorize`).

For each group in the request:
1. Create `RecurringPayment(name=name, is_income=is_income, category=category)`
2. For each transaction ID, fetch the transaction and create a `Bill`:
   - `description=txn.description`, `due_date=txn.when.date()`, `due_amount=abs(txn.amount)`
   - `series=recurring_payment`
   - Set `paying_transactions` M2M to include the transaction
3. Return the created RecurringPayment objects using existing `RecurringPaymentSerializer`.

---

### Task 1E: Tests

**New file:** `ctrack/test_recurring_detection.py` — unit tests for detection algorithm

Follow the test patterns from `ctrack/test_category_groups.py`:
- `django.test.TestCase` for model/unit tests
- `rest_framework.test.APITestCase` for API tests
- `self.client.force_authenticate(user=self.user)` for auth
- Create synthetic data in `setUp`

**Unit test cases:**
1. Synthetic monthly pattern (12 transactions, same description "Vodafone Payment", fixed -$50 monthly) → detected as monthly/fixed
2. Synthetic weekly pattern (26 transactions, "Woolworths", varying amounts around -$80) → detected as weekly/variable
3. Random non-recurring transactions (different descriptions, random dates) → not detected (noise)
4. Edge cases: empty queryset, all null descriptions, single transaction, identical dates within cluster
5. Mixed: monthly + weekly patterns in same dataset both detected correctly

**New file:** `ctrack/test_recurring_detection_api.py` — API integration tests

**API test cases:**
1. `POST /api/payments/detect_recurring/` with 12+ months of synthetic data returns expected groups
2. Insufficient data (<20 transactions) returns 400
3. Account filter correctly scopes detection
4. `POST /api/payments/create_from_detection/` creates correct RecurringPayment + Bill objects
5. Created Bills have `paying_transactions` M2M set correctly
6. Invalid transaction IDs in `create_from_detection` returns 400

---

### Phase 1 Files Summary

| File | Action |
|------|--------|
| `ctrack/models.py` | **Modify**: add `category` FK to `RecurringPayment` (~line 312) |
| `ctrack/migrations/00XX_*.py` | **Auto-generated**: migration for new FK |
| `ctrack/recurring_detection.py` | **New**: `RecurringTransactionDetector` class |
| `ctrack/api/serializers/recurring_detection.py` | **New**: request/response serializers |
| `ctrack/api/recurring_payment.py` | **Modify**: add `detect_recurring` + `create_from_detection` actions, update `RecurringPaymentSerializer` |
| `ctrack/test_recurring_detection.py` | **New**: unit tests for algorithm |
| `ctrack/test_recurring_detection_api.py` | **New**: API integration tests |

### Phase 1 Verification

```bash
python manage.py makemigrations   # generates migration
python manage.py migrate           # applies it
python manage.py test ctrack.test_recurring_detection
python manage.py test ctrack.test_recurring_detection_api
python manage.py test              # full suite still passes
```

---

## Phase 2: Progress Tracking API

**Depends on Phase 1** (uses `RecurringPayment.category` FK for mapping bills to categories).

### Task 2A: Progress View + Serializers

**New file:** `ctrack/api/progress.py`

An `APIView` (not ViewSet) following the pattern of `PeriodDefinitionView` in `ctrack/api/period_definition.py` and `CategorySummary` in `ctrack/api/categories.py:74-101`.

**Query parameters:**
- `period` (required unless `from_date`/`to_date` provided): `week`, `month`, `quarter`, or a numeric `PeriodDefinition` id
- `from_date` / `to_date` (optional): explicit date range override (format: YYYY-MM-DD)
- `group_by` (optional, default `category`): `category` or `category_group`

**Response:**
```json
{
  "period": { "from_date": "2026-04-01", "to_date": "2026-04-30", "label": "Month" },
  "rows": [
    {
      "id": 5,
      "name": "Food - Groceries",
      "actual_spend": -342.50,
      "expected_remaining": -157.50,
      "budget": -500.00,
      "upcoming_bills": [
        { "name": "HelloFresh", "expected_date": "2026-04-18", "expected_amount": 89.00 }
      ]
    }
  ],
  "totals": { "actual_spend": -1250.00, "expected_remaining": -480.00, "budget": -2000.00 }
}
```

**Serializers (in same file):**
```python
class ProgressPeriodSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    label = serializers.CharField()

class UpcomingBillSerializer(serializers.Serializer):
    name = serializers.CharField()
    expected_date = serializers.DateField()
    expected_amount = serializers.DecimalField(max_digits=8, decimal_places=2)

class ProgressRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    actual_spend = serializers.DecimalField(max_digits=20, decimal_places=2)
    expected_remaining = serializers.DecimalField(max_digits=20, decimal_places=2)
    budget = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)
    upcoming_bills = UpcomingBillSerializer(many=True)

class ProgressTotalsSerializer(serializers.Serializer):
    actual_spend = serializers.DecimalField(max_digits=20, decimal_places=2)
    expected_remaining = serializers.DecimalField(max_digits=20, decimal_places=2)
    budget = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)

class ProgressResponseSerializer(serializers.Serializer):
    period = ProgressPeriodSerializer()
    rows = ProgressRowSerializer(many=True)
    totals = ProgressTotalsSerializer()
```

### Task 2B: View Logic

**`ProgressView.get()` method steps:**

**Step 1 — Resolve period:**
```python
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

today = date.today()
period = request.query_params.get('period')
from_date = request.query_params.get('from_date')
to_date = request.query_params.get('to_date')

if from_date and to_date:
    from_date = parse_date(from_date)
    to_date = parse_date(to_date)
    label = "Custom"
elif period == "week":
    from_date = today - timedelta(days=today.weekday())  # Monday
    to_date = from_date + timedelta(days=6)
    label = "Week"
elif period == "month":
    from_date = today.replace(day=1)
    to_date = (from_date + relativedelta(months=1)) - timedelta(days=1)
    label = "Month"
elif period == "quarter":
    q_start = ((today.month - 1) // 3) * 3 + 1
    from_date = date(today.year, q_start, 1)
    to_date = (from_date + relativedelta(months=3)) - timedelta(days=1)
    label = "Quarter"
elif period and period.isdigit():
    pd_obj = PeriodDefinition.objects.get(pk=int(period))
    from_date, to_date = pd_obj.current
    label = pd_obj.label
else:
    return Response({"detail": "..."}, status=400)
```

**Step 2 — Actual spend:**

For `group_by=category`:
```python
Transaction.objects.filter(
    when__gte=from_date, when__lte=to_date, is_split=False
).values('category', 'category__name').annotate(actual_spend=Sum('amount'))
```

For `group_by=category_group`: iterate `CategoryGroup.objects.all()`, filter transactions where `category__in=group.categories.all()`, aggregate Sum.

**Step 3 — Budget allocation:**

Reuse `BudgetEntry.objects.for_period(to_date)` (`ctrack/models.py:401`) and `entry.amount_over_period(from_date, to_date)` (`ctrack/models.py:422`). Map budget entries to categories via `.categories` M2M.

**Step 4 — Expected remaining spend** (two sources, budget preferred with historical fallback):

- **Budget pro-rata**: For categories with a `BudgetEntry`, compute `entry.amount_over_period(remaining_start, to_date)` where `remaining_start = max(today + timedelta(days=1), from_date)`.
- **Historical average fallback**: For categories without a budget, compute average daily spend from the 90 days prior to `from_date`:
  ```python
  history_start = from_date - timedelta(days=90)
  daily_avg = Transaction.objects.filter(
      category=cat, when__gte=history_start, when__lt=from_date, is_split=False
  ).aggregate(total=Sum('amount'))['total'] or 0
  daily_avg = float(daily_avg) / 90
  expected = daily_avg * remaining_days
  ```

**Step 5 — Upcoming recurring bills:**

For each `RecurringPayment.objects.filter(is_income=False, category__isnull=False)`:
1. Call `payment.next_due_date()` (`ctrack/models.py:321`)
2. If next date falls within `(today, to_date]`, include it
3. Step forward by mean interval to catch multiple bills within period (e.g., weekly bills)
4. Use latest bill amount as expected amount: `payment.bills_as_series().iloc[-1]`
5. Map to category row via `payment.category` FK

**Step 6 — Assemble response**: Build row dicts, compute totals, serialize.

### Task 2C: Wire Up URL

**Modify:** `ctrack/api/__init__.py` — add before the router catch-all (line 31):
```python
from ctrack.api.progress import ProgressView
# In urls list:
re_path(r'^progress/$', ProgressView.as_view()),
```

### Task 2D: Tests

**New file:** `ctrack/test_progress_api.py`

Follow patterns from `ctrack/test_category_groups.py:65-80` for setUp.

**Test cases:**
1. `test_progress_month` — period resolution, correct date range in response
2. `test_progress_week` — Monday-Sunday range
3. `test_progress_quarter` — calendar quarter range
4. `test_progress_explicit_dates` — from_date/to_date override
5. `test_progress_period_id` — PeriodDefinition lookup
6. `test_progress_actual_spend_by_category` — correct aggregation
7. `test_progress_actual_spend_by_category_group` — group_by=category_group
8. `test_progress_budget_amounts` — budget correctly scaled to period
9. `test_progress_expected_remaining_budget` — uses budget pro-rata for remaining days
10. `test_progress_expected_remaining_historical` — falls back to historical average when no budget
11. `test_progress_upcoming_bills` — RecurringPayment predictions appear in correct category
12. `test_progress_excludes_splits` — is_split=True excluded
13. `test_progress_missing_period` — returns 400
14. `test_progress_totals` — totals sum correctly

---

### Phase 2 Files Summary

| File | Action |
|------|--------|
| `ctrack/api/progress.py` | **New**: ProgressView, serializers, period logic |
| `ctrack/api/__init__.py` | **Modify**: add URL wiring (line ~31) |
| `ctrack/test_progress_api.py` | **New**: API tests |

### Phase 2 Verification

```bash
python manage.py test ctrack.test_progress_api
python manage.py test   # full suite still passes
```

---

## Existing Code to Reuse

| What | Where |
|------|-------|
| `BudgetEntry.objects.for_period(date)` | `ctrack/models.py:401` |
| `BudgetEntry.amount_over_period(from_date, to_date)` | `ctrack/models.py:422-426` |
| `RecurringPayment.next_due_date()` | `ctrack/models.py:321-331` |
| `RecurringPayment.bills_as_series()` | `ctrack/models.py:314-319` |
| `PeriodDefinition.current` | `ctrack/models.py:248-249` |
| `PeriodDefinition.date_ranges` | `ctrack/models.py:240-245` |
| TF-IDF vectorization pattern | `ctrack/categories.py:101-102` |
| Preview-then-apply API pattern | `ctrack/api/categorisor.py:340-388` |
| Transaction filtering `is_split=False` | Used throughout API views |
| Test setUp patterns | `ctrack/test_category_groups.py:65-80` |
| Custom Serializer pattern | `ctrack/api/categories.py:31-35` (CategorySummarySerializer) |
| Date range filtering | `ctrack/api/transactions.py:54-63` (DateRangeTransactionFilter) |

## Agent Task Breakdown

Each task below is independently implementable:

| Task | Depends On | Scope |
|------|-----------|-------|
| **1A**: Model change + migration | Nothing | Small: 2 lines in models.py, 1 line in serializer, run makemigrations |
| **1B**: Core detection algorithm | Nothing | Medium: new file `recurring_detection.py` (~150 lines) |
| **1C**: Serializers | Nothing | Small: new file with serializer classes (~60 lines) |
| **1D**: API endpoints | 1A, 1B, 1C | Medium: modify `recurring_payment.py` (~80 lines added) |
| **1E**: Phase 1 tests | 1A, 1B, 1C, 1D | Medium: two new test files (~200 lines each) |
| **2A+2B**: Progress view | 1A | Medium-large: new file `progress.py` (~200 lines) |
| **2C**: URL wiring | 2A | Tiny: 2 lines in `__init__.py` |
| **2D**: Phase 2 tests | 2A, 2B, 2C | Medium: new test file (~250 lines) |

**Suggested parallel execution:** Tasks 1A, 1B, 1C can run in parallel. Then 1D. Then 1E and 2A+2B in parallel. Then 2C+2D.
