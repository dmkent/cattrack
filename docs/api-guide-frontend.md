# CatTrack API Guide for React Frontend

## Base URL & Auth
- Base URL: `/api/`
- Authentication: JWT (via `djangorestframework-simplejwt`). Include `Authorization: Bearer <token>` header.
- CORS is configured via `django-cors-headers`.

---

## 1. Progress Tracking

### `GET /api/progress/`

Returns actual spend, expected remaining spend, budget, and upcoming bills for a period, grouped by category or category group.

**Query Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `period` | string | `"week"`, `"month"`, `"quarter"`, or a `PeriodDefinition` ID (integer) |
| `from_date` | date (YYYY-MM-DD) | Start of custom range (use with `to_date` instead of `period`) |
| `to_date` | date (YYYY-MM-DD) | End of custom range |
| `group_by` | string | `"category"` (default) or `"category_group"` |

Must provide either `period` OR both `from_date`/`to_date`.

**Response (200):**
```json
{
  "period": {
    "from_date": "2026-04-01",
    "to_date": "2026-04-30",
    "label": "This month"
  },
  "rows": [
    {
      "id": 5,
      "name": "Groceries",
      "actual_spend": "-342.50",
      "expected_remaining": "-157.50",
      "budget": "-500.00",
      "upcoming_bills": []
    },
    {
      "id": 8,
      "name": "Utilities",
      "actual_spend": "-89.00",
      "expected_remaining": "-45.00",
      "budget": "-150.00",
      "upcoming_bills": [
        {
          "name": "Electricity",
          "expected_date": "2026-04-15",
          "expected_amount": "120.00"
        }
      ]
    }
  ],
  "totals": {
    "actual_spend": "-431.50",
    "expected_remaining": "-202.50",
    "budget": "-650.00"
  }
}
```

**Notes:**
- Amounts are negative for expenses, positive for income.
- `budget` is `null` for rows/totals where no budget entry exists.
- `expected_remaining` uses pro-rated budget for budgeted categories, or 90-day historical average for unbudgeted categories.
- `upcoming_bills` lists recurring payments due between today and the period end.

**Error (400):** `{"detail": "Provide 'period' or both 'from_date' and 'to_date'."}`

---

## 2. Recurring Transaction Detection

### `POST /api/payments/detect_recurring/`

Runs ML clustering to find recurring transaction patterns in historical data.

**Request Body (JSON):**
```json
{
  "from_date": "2025-04-01",
  "to_date": "2026-04-01",
  "min_cluster_size": 3,
  "interval_cv_threshold": 0.35,
  "cosine_distance_threshold": 0.4,
  "amount_tolerance": 0.10,
  "account": 1
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `from_date` | date | yes | — | Start of analysis window (12+ months recommended) |
| `to_date` | date | yes | — | End of analysis window |
| `min_cluster_size` | int | no | 3 | Min transactions to form a cluster (2–20) |
| `interval_cv_threshold` | float | no | 0.35 | Max coefficient of variation for regularity (0.1–1.0) |
| `cosine_distance_threshold` | float | no | 0.4 | Max cosine distance for description clustering (0.1–0.9) |
| `amount_tolerance` | float | no | 0.10 | Fraction of median amount for sub-grouping (0.01–0.5) |
| `account` | int | no | — | Filter to a specific account ID |

**Response (200):**
```json
{
  "status": "ok",
  "total_transactions": 847,
  "groups_found": 12,
  "groups": [
    {
      "cluster_id": 0,
      "description_pattern": "VODAFONE PAYMENT",
      "sample_descriptions": ["VODAFONE PAYMENT"],
      "frequency": "monthly",
      "mean_interval_days": 30.2,
      "interval_cv": 0.05,
      "regularity_score": 0.95,
      "amount_mean": -65.00,
      "amount_std": 0.00,
      "amount_type": "fixed",
      "is_income": false,
      "transaction_count": 12,
      "transaction_ids": [101, 145, 189],
      "first_date": "2025-04-15",
      "last_date": "2026-03-15",
      "category": 5,
      "category_name": "Phone"
    }
  ]
}
```

**Key fields for UI:**
- `frequency`: one of `"weekly"`, `"fortnightly"`, `"monthly"`, `"quarterly"`, `"semi_annual"`, `"annual"`, `"irregular"`
- `amount_type`: `"fixed"`, `"variable_low"`, `"variable_high"`
- `regularity_score`: 0.0–1.0 (higher = more regular)
- `category`/`category_name`: auto-inferred from most common category in the transactions (can be `null`)

**Error (400):** `{"status": "error", "detail": "Need at least 20 transactions with descriptions."}`

---

### `POST /api/payments/create_from_detection/`

Creates `RecurringPayment` + `Bill` records from user-selected detected groups. Typically called after the user reviews `detect_recurring` results and selects which groups to save.

**Request Body (JSON):**
```json
{
  "groups": [
    {
      "name": "Vodafone",
      "transaction_ids": [101, 145, 189],
      "is_income": false,
      "category": 5
    },
    {
      "name": "Salary",
      "transaction_ids": [110, 155, 200],
      "is_income": true,
      "category": 2
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `groups[].name` | string | yes | Name for the recurring payment (max 100 chars) |
| `groups[].transaction_ids` | int[] | yes | Transaction IDs from the detection results |
| `groups[].is_income` | bool | no | Default `false` |
| `groups[].category` | int | no | Category FK (nullable) |

**Response (201):** Array of created `RecurringPayment` objects:
```json
[
  {
    "url": "http://localhost:8000/api/payments/1/",
    "id": 1,
    "name": "Vodafone",
    "is_income": false,
    "bills": [
      {
        "id": 1,
        "description": "VODAFONE PAYMENT",
        "due_date": "2025-04-15",
        "due_amount": "65.00"
      }
    ],
    "next_due_date": "2026-04-15",
    "category": 5
  }
]
```

**Error (400):** `{"detail": "Transaction IDs not found: [999, 1000]"}`

The operation is atomic — if any group fails validation, nothing is created.

---

## 3. Standard CRUD Endpoints (DRF Router)

All are standard `ModelViewSet` endpoints supporting `GET` (list/detail), `POST`, `PUT`, `PATCH`, `DELETE`.

| Endpoint | Description |
|----------|-------------|
| `GET /api/accounts/` | Bank accounts |
| `GET /api/categories/` | Spending categories |
| `GET /api/category-groups/` | Category groups (collections of categories) |
| `GET /api/transactions/` | Transactions (supports filtering) |
| `GET /api/payments/` | Recurring payments |
| `GET /api/payments/{id}/` | Single recurring payment with nested `bills` |
| `GET /api/bills/` | Bills (filterable by `due_date`, `series`) |
| `GET /api/budget/` | Budget entries |
| `GET /api/periods/` | Period definitions |
| `GET /api/user-settings/` | User settings |

---

## 4. Suggested Frontend Workflow

### Progress Tracking View
1. Let user pick a period via a selector (`week`/`month`/`quarter` or custom dates)
2. Optionally toggle `group_by` between `category` and `category_group`
3. Call `GET /api/progress/?period=month&group_by=category`
4. Render rows as a table or bar chart showing `actual_spend` vs `budget` vs `expected_remaining`
5. Show `upcoming_bills` as a detail/expandable section per row
6. Show `totals` as a summary row/card

### Recurring Detection View
1. User selects a date range (default: last 12 months) and optionally an account
2. Call `POST /api/payments/detect_recurring/` with the parameters
3. Display detected groups as a list/table, sorted by `regularity_score`
4. Let user select which groups to save (checkboxes), optionally editing the `name` and `category`
5. Call `POST /api/payments/create_from_detection/` with selected groups
6. Show confirmation with created recurring payments
