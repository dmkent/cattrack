"""Progress tracking API — shows actual vs budget vs expected spend."""

import calendar
import logging
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.utils.dateparse import parse_date
from rest_framework import response, serializers, views

from ctrack.models import (
    BudgetEntry,
    Category,
    CategoryGroup,
    PeriodDefinition,
    RecurringPayment,
    Transaction,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class ProgressView(views.APIView):
    """GET /api/progress/ — progress tracking for a given period."""

    def get(self, request, format=None):
        today = date.today()

        # ------------------------------------------------------------------
        # Step 1 — Resolve period
        # ------------------------------------------------------------------
        from_date, to_date, label = self._resolve_period(request, today)
        if from_date is None:
            return response.Response(
                {"detail": "Provide 'period' or both 'from_date' and 'to_date'."},
                status=400,
            )

        group_by = request.query_params.get("group_by", "category")

        # ------------------------------------------------------------------
        # Step 2 — Actual spend by category or category_group
        # ------------------------------------------------------------------
        if group_by == "category_group":
            spend_map = self._spend_by_category_group(from_date, to_date)
        else:
            spend_map = self._spend_by_category(from_date, to_date)

        # ------------------------------------------------------------------
        # Step 3 — Budget amounts mapped to rows
        # ------------------------------------------------------------------
        budget_entries = BudgetEntry.objects.for_period(to_date)
        # budget_map: row_id -> budget amount over the period
        budget_map = {}
        # category_to_row: category_pk -> row_id  (for bill mapping later)
        category_to_row = {}
        # budgeted_category_pks: set of category PKs that have a budget
        budgeted_category_pks = set()

        for entry in budget_entries:
            budget_amount = entry.amount_over_period(from_date, to_date)
            cat_pks = set(entry.categories.values_list("pk", flat=True))
            n_cats = len(cat_pks)
            budgeted_category_pks |= cat_pks

            if group_by == "category_group":
                # Map budget to groups that contain any of the entry's categories
                matching_groups = list(
                    CategoryGroup.objects.filter(categories__in=cat_pks).distinct()
                )
                n_groups = len(matching_groups) or 1
                per_group_amount = Decimal(str(budget_amount)) / n_groups
                for group in matching_groups:
                    budget_map.setdefault(group.pk, Decimal("0"))
                    budget_map[group.pk] += per_group_amount
                    for cpk in cat_pks:
                        category_to_row[cpk] = group.pk
            else:
                # Pro-rate across categories so the total isn't duplicated
                per_cat_amount = Decimal(str(budget_amount)) / (n_cats or 1)
                for cpk in cat_pks:
                    budget_map.setdefault(cpk, Decimal("0"))
                    budget_map[cpk] += per_cat_amount
                    category_to_row[cpk] = cpk

        # ------------------------------------------------------------------
        # Step 4 — Expected remaining spend
        # ------------------------------------------------------------------
        remaining_start = max(today + timedelta(days=1), from_date)
        remaining_days = (to_date - remaining_start).days + 1 if remaining_start <= to_date else 0

        expected_remaining_map = {}

        if remaining_days > 0:
            # Pro-rata budget for categories WITH a budget
            for entry in budget_entries:
                remaining_amount = Decimal(
                    str(entry.amount_over_period(remaining_start, to_date))
                )
                cat_pks = set(entry.categories.values_list("pk", flat=True))
                n_cats = len(cat_pks)

                if group_by == "category_group":
                    matching_groups = list(
                        CategoryGroup.objects.filter(
                            categories__in=cat_pks
                        ).distinct()
                    )
                    n_groups = len(matching_groups) or 1
                    per_group_amount = remaining_amount / n_groups
                    for group in matching_groups:
                        expected_remaining_map.setdefault(group.pk, Decimal("0"))
                        expected_remaining_map[group.pk] += per_group_amount
                else:
                    per_cat_amount = remaining_amount / (n_cats or 1)
                    for cpk in cat_pks:
                        expected_remaining_map.setdefault(cpk, Decimal("0"))
                        expected_remaining_map[cpk] += per_cat_amount

            # Historical average fallback for categories WITHOUT a budget
            lookback_start = from_date - timedelta(days=90)
            lookback_end = from_date - timedelta(days=1)
            lookback_days = (lookback_end - lookback_start).days or 1

            if group_by == "category_group":
                for group in CategoryGroup.objects.all():
                    if group.pk not in budget_map:
                        hist = (
                            Transaction.objects.filter(
                                when__gte=lookback_start,
                                when__lte=lookback_end,
                                is_split=False,
                                category__in=group.categories.all(),
                            ).aggregate(total=Sum("amount"))["total"]
                            or Decimal("0")
                        )
                        avg_daily = hist / lookback_days
                        expected_remaining_map[group.pk] = avg_daily * remaining_days
            else:
                # Find categories that appeared in spend_map but have no budget
                unbudgeted_cats = set(spend_map.keys()) - budgeted_category_pks
                if unbudgeted_cats:
                    hist_qs = (
                        Transaction.objects.filter(
                            when__gte=lookback_start,
                            when__lte=lookback_end,
                            is_split=False,
                            category__in=unbudgeted_cats,
                        )
                        .values("category")
                        .annotate(total=Sum("amount"))
                    )
                    for row in hist_qs:
                        avg_daily = row["total"] / lookback_days
                        expected_remaining_map[row["category"]] = (
                            avg_daily * remaining_days
                        )

        # ------------------------------------------------------------------
        # Step 5 — Upcoming recurring bills
        # ------------------------------------------------------------------
        upcoming_map = {}  # row_id -> list of bill dicts

        for payment in RecurringPayment.objects.filter(
            is_income=False, category__isnull=False
        ):
            ndd = payment.next_due_date()
            if ndd is None:
                continue
            # next_due_date may return a pandas Timestamp; normalise to date
            if hasattr(ndd, "date"):
                ndd = ndd.date()

            series = payment.bills_as_series()
            if len(series) < 2:
                mean_interval = None
            else:
                days_between = series.index.to_series().diff().dt.days.dropna()
                mean_interval = int(days_between.mean()) if len(days_between) else None

            expected_amount = Decimal(str(abs(float(series.iloc[-1])))) if len(series) else Decimal("0")

            # Determine the row this payment maps to
            cat_pk = payment.category_id
            if group_by == "category_group":
                groups = CategoryGroup.objects.filter(categories=cat_pk)
                row_ids = [g.pk for g in groups]
            else:
                row_ids = [cat_pk]

            # Walk through due dates within the period
            due = ndd
            while due is not None and due <= to_date:
                if due > today:
                    bill_dict = {
                        "name": payment.name,
                        "expected_date": due,
                        "expected_amount": expected_amount,
                    }
                    for rid in row_ids:
                        upcoming_map.setdefault(rid, []).append(bill_dict)
                # Step forward
                if mean_interval and mean_interval > 0:
                    due = due + timedelta(days=mean_interval)
                else:
                    break

        # ------------------------------------------------------------------
        # Step 6 — Assemble response
        # ------------------------------------------------------------------
        all_ids = set(spend_map.keys()) | set(budget_map.keys()) | set(
            expected_remaining_map.keys()
        ) | set(upcoming_map.keys())

        # Remove None keys (uncategorised transactions)
        all_ids.discard(None)

        # Build a name lookup
        if group_by == "category_group":
            name_lookup = dict(
                CategoryGroup.objects.filter(pk__in=all_ids).values_list("pk", "name")
            )
        else:
            name_lookup = dict(
                Category.objects.filter(pk__in=all_ids).values_list("pk", "name")
            )

        rows = []
        for row_id in sorted(all_ids, key=lambda rid: name_lookup.get(rid, "")):
            rows.append(
                {
                    "id": row_id,
                    "name": name_lookup.get(row_id, "Unknown"),
                    "actual_spend": spend_map.get(row_id, Decimal("0")),
                    "expected_remaining": expected_remaining_map.get(
                        row_id, Decimal("0")
                    ),
                    "budget": budget_map.get(row_id, None),
                    "upcoming_bills": upcoming_map.get(row_id, []),
                }
            )

        total_actual = sum(r["actual_spend"] for r in rows)
        total_expected = sum(r["expected_remaining"] for r in rows)
        budget_values = [r["budget"] for r in rows if r["budget"] is not None]
        total_budget = sum(budget_values) if budget_values else None

        data = {
            "period": {
                "from_date": from_date,
                "to_date": to_date,
                "label": label,
            },
            "rows": rows,
            "totals": {
                "actual_spend": total_actual,
                "expected_remaining": total_expected,
                "budget": total_budget,
            },
        }

        serializer = ProgressResponseSerializer(data)
        return response.Response(serializer.data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_period(request, today):
        """Return (from_date, to_date, label) or (None, None, None)."""
        # Explicit date range takes priority
        raw_from = request.query_params.get("from_date")
        raw_to = request.query_params.get("to_date")
        if raw_from and raw_to:
            parsed_from = parse_date(raw_from)
            parsed_to = parse_date(raw_to)
            if parsed_from is None or parsed_to is None:
                return None, None, None
            if parsed_from > parsed_to:
                return None, None, None
            return parsed_from, parsed_to, "Custom"

        period = request.query_params.get("period")
        if not period:
            return None, None, None

        if period == "week":
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            return monday, sunday, "This week"

        if period == "month":
            first = today.replace(day=1)
            last_day = calendar.monthrange(today.year, today.month)[1]
            last = today.replace(day=last_day)
            return first, last, "This month"

        if period == "quarter":
            q_month = ((today.month - 1) // 3) * 3 + 1
            first = date(today.year, q_month, 1)
            last = first + relativedelta(months=3) - timedelta(days=1)
            return first, last, "This quarter"

        # Numeric — PeriodDefinition pk
        try:
            pd_obj = PeriodDefinition.objects.get(pk=int(period))
            from_date, to_date = pd_obj.current
            # PeriodDefinition dates may be pandas Timestamps
            if hasattr(from_date, "date"):
                from_date = from_date.date()
            if hasattr(to_date, "date"):
                to_date = to_date.date()
            return from_date, to_date, "Current " + pd_obj.label
        except (ValueError, PeriodDefinition.DoesNotExist):
            return None, None, None

    @staticmethod
    def _spend_by_category(from_date, to_date):
        """Return {category_pk: Decimal spend} for the period.

        Excludes uncategorised transactions (category=NULL).
        """
        qs = (
            Transaction.objects.filter(
                when__gte=from_date, when__lte=to_date,
                is_split=False, category__isnull=False,
            )
            .values("category", "category__name")
            .annotate(actual_spend=Sum("amount"))
        )
        return {row["category"]: row["actual_spend"] or Decimal("0") for row in qs}

    @staticmethod
    def _spend_by_category_group(from_date, to_date):
        """Return {group_pk: Decimal spend} for the period.

        Uses a single query with annotation instead of N+1 per-group queries.
        """
        # Fetch all transactions in the period, grouped by category
        cat_totals = dict(
            Transaction.objects.filter(
                when__gte=from_date, when__lte=to_date,
                is_split=False, category__isnull=False,
            )
            .values_list("category")
            .annotate(total=Sum("amount"))
        )

        # Map category totals to groups
        spend_map = {}
        for group in CategoryGroup.objects.prefetch_related("categories").all():
            total = sum(
                cat_totals.get(cat_pk, Decimal("0"))
                for cat_pk in group.categories.values_list("pk", flat=True)
            )
            if total:
                spend_map[group.pk] = total
        return spend_map
