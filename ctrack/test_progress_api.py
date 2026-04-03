"""Tests for the Progress tracking API endpoint."""

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytz
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from ctrack import models


class ProgressAPITestCase(APITestCase):
    """Test GET /api/progress/ endpoint."""

    def setUp(self):
        """Create user, categories, group, account, budget, recurring payment, bills, and transactions."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        # Categories
        self.groceries = models.Category.objects.create(name="Groceries")
        self.bills_power = models.Category.objects.create(name="Bills - Power")
        self.entertainment = models.Category.objects.create(name="Entertainment")

        # CategoryGroup containing Groceries
        self.food_group = models.CategoryGroup.objects.create(name="Food")
        self.food_group.categories.add(self.groceries)

        # Account
        self.account = models.Account.objects.create(name="Test Account")

        # BudgetEntry for Groceries, valid for current year, monthly amount 500
        today = date.today()
        self.budget_entry = models.BudgetEntry.objects.create(
            name="Groceries Budget",
            amount=Decimal("500.00"),
            valid_from=date(today.year, 1, 1),
            valid_to=date(today.year, 12, 31),
        )
        self.budget_entry.categories.add(self.groceries)

        # RecurringPayment (expense) for Bills - Power
        self.recurring = models.RecurringPayment.objects.create(
            name="Electricity",
            is_income=False,
            category=self.bills_power,
        )

        # Create 3 Bills with regular monthly due_dates
        # Use dates that ensure next_due_date falls within the current month
        for i in range(3):
            month_offset = today.month - 3 + i
            year = today.year
            while month_offset < 1:
                month_offset += 12
                year -= 1
            while month_offset > 12:
                month_offset -= 12
                year += 1
            bill_date = date(year, month_offset, 15)
            models.Bill.objects.create(
                description="Electricity",
                due_date=bill_date,
                due_amount=Decimal("120.00"),
                series=self.recurring,
            )

        # Transactions within current month
        self.tx1 = models.Transaction.objects.create(
            when=datetime(today.year, today.month, 1, 10, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=Decimal("45.50"),
            category=self.groceries,
            description="Supermarket",
        )
        self.tx2 = models.Transaction.objects.create(
            when=datetime(today.year, today.month, 2, 14, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=Decimal("30.00"),
            category=self.groceries,
            description="Farmers market",
        )
        self.tx3 = models.Transaction.objects.create(
            when=datetime(today.year, today.month, 3, 9, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=Decimal("120.00"),
            category=self.bills_power,
            description="Power bill",
        )
        self.tx4 = models.Transaction.objects.create(
            when=datetime(today.year, today.month, 1, 20, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=Decimal("15.00"),
            category=self.entertainment,
            description="Movie ticket",
        )

    # ------------------------------------------------------------------
    # 1. test_progress_month
    # ------------------------------------------------------------------
    def test_progress_month(self):
        """GET with period=month returns first/last day of current month and rows."""
        response = self.client.get("/api/progress/", {"period": "month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        today = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]

        period = response.data["period"]
        self.assertEqual(period["from_date"], str(today.replace(day=1)))
        self.assertEqual(period["to_date"], str(today.replace(day=last_day)))
        self.assertEqual(period["label"], "This month")
        self.assertGreater(len(response.data["rows"]), 0)

    # ------------------------------------------------------------------
    # 2. test_progress_week
    # ------------------------------------------------------------------
    def test_progress_week(self):
        """GET with period=week returns Monday-Sunday range."""
        response = self.client.get("/api/progress/", {"period": "week"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        today = date.today()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        period = response.data["period"]
        self.assertEqual(period["from_date"], str(monday))
        self.assertEqual(period["to_date"], str(sunday))
        self.assertEqual(period["label"], "This week")

    # ------------------------------------------------------------------
    # 3. test_progress_quarter
    # ------------------------------------------------------------------
    def test_progress_quarter(self):
        """GET with period=quarter returns calendar quarter range."""
        response = self.client.get("/api/progress/", {"period": "quarter"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        today = date.today()
        q_month = ((today.month - 1) // 3) * 3 + 1
        quarter_start = date(today.year, q_month, 1)
        # End of quarter: 3 months later minus 1 day
        if q_month + 3 <= 12:
            quarter_end = date(today.year, q_month + 3, 1) - timedelta(days=1)
        else:
            quarter_end = date(today.year + 1, 1, 1) - timedelta(days=1)

        period = response.data["period"]
        self.assertEqual(period["from_date"], str(quarter_start))
        self.assertEqual(period["to_date"], str(quarter_end))
        self.assertEqual(period["label"], "This quarter")

    # ------------------------------------------------------------------
    # 4. test_progress_explicit_dates
    # ------------------------------------------------------------------
    def test_progress_explicit_dates(self):
        """GET with from_date/to_date params uses those dates."""
        response = self.client.get(
            "/api/progress/",
            {"from_date": "2026-03-01", "to_date": "2026-03-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        period = response.data["period"]
        self.assertEqual(period["from_date"], "2026-03-01")
        self.assertEqual(period["to_date"], "2026-03-31")
        self.assertEqual(period["label"], "Custom")

    # ------------------------------------------------------------------
    # 5. test_progress_missing_period
    # ------------------------------------------------------------------
    def test_progress_missing_period(self):
        """GET with no params returns 400."""
        response = self.client.get("/api/progress/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    # ------------------------------------------------------------------
    # 6. test_progress_actual_spend_by_category
    # ------------------------------------------------------------------
    def test_progress_actual_spend_by_category(self):
        """Actual spend sums correctly per category for the current month."""
        response = self.client.get("/api/progress/", {"period": "month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rows_by_name = {r["name"]: r for r in response.data["rows"]}

        # Groceries: 45.50 + 30.00 = 75.50
        self.assertIn("Groceries", rows_by_name)
        self.assertEqual(
            Decimal(rows_by_name["Groceries"]["actual_spend"]),
            Decimal("75.50"),
        )

        # Bills - Power: 120.00
        self.assertIn("Bills - Power", rows_by_name)
        self.assertEqual(
            Decimal(rows_by_name["Bills - Power"]["actual_spend"]),
            Decimal("120.00"),
        )

        # Entertainment: 15.00
        self.assertIn("Entertainment", rows_by_name)
        self.assertEqual(
            Decimal(rows_by_name["Entertainment"]["actual_spend"]),
            Decimal("15.00"),
        )

    # ------------------------------------------------------------------
    # 7. test_progress_actual_spend_by_category_group
    # ------------------------------------------------------------------
    def test_progress_actual_spend_by_category_group(self):
        """group_by=category_group aggregates spend by group."""
        response = self.client.get(
            "/api/progress/",
            {"period": "month", "group_by": "category_group"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rows_by_name = {r["name"]: r for r in response.data["rows"]}

        # Food group contains Groceries: 45.50 + 30.00 = 75.50
        self.assertIn("Food", rows_by_name)
        self.assertEqual(
            Decimal(rows_by_name["Food"]["actual_spend"]),
            Decimal("75.50"),
        )

    # ------------------------------------------------------------------
    # 8. test_progress_budget_amounts
    # ------------------------------------------------------------------
    def test_progress_budget_amounts(self):
        """Budget field matches BudgetEntry.amount_over_period for the period."""
        response = self.client.get("/api/progress/", {"period": "month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        today = date.today()
        first = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        last = today.replace(day=last_day)
        expected_budget = self.budget_entry.amount_over_period(first, last)

        rows_by_name = {r["name"]: r for r in response.data["rows"]}
        self.assertIn("Groceries", rows_by_name)
        self.assertAlmostEqual(
            float(rows_by_name["Groceries"]["budget"]),
            expected_budget,
            places=2,
        )

    # ------------------------------------------------------------------
    # 9. test_progress_excludes_splits
    # ------------------------------------------------------------------
    def test_progress_excludes_splits(self):
        """is_split=True transactions are not included in actual_spend."""
        # Create a split transaction in Groceries
        today = date.today()
        models.Transaction.objects.create(
            when=datetime(today.year, today.month, 4, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=Decimal("200.00"),
            category=self.groceries,
            description="Split parent",
            is_split=True,
        )

        response = self.client.get("/api/progress/", {"period": "month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        rows_by_name = {r["name"]: r for r in response.data["rows"]}
        # Should still be 75.50, the split transaction excluded
        self.assertEqual(
            Decimal(rows_by_name["Groceries"]["actual_spend"]),
            Decimal("75.50"),
        )

    # ------------------------------------------------------------------
    # 10. test_progress_totals
    # ------------------------------------------------------------------
    def test_progress_totals(self):
        """totals.actual_spend equals sum of row actual_spend values."""
        response = self.client.get("/api/progress/", {"period": "month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row_sum = sum(
            Decimal(r["actual_spend"]) for r in response.data["rows"]
        )
        self.assertEqual(
            Decimal(response.data["totals"]["actual_spend"]),
            row_sum,
        )

    # ------------------------------------------------------------------
    # 11. test_progress_upcoming_bills
    # ------------------------------------------------------------------
    def test_progress_upcoming_bills(self):
        """upcoming_bills appear for RecurringPayment category when next_due_date is within period."""
        # Use a quarter period to increase chance of capturing the next due date
        response = self.client.get("/api/progress/", {"period": "quarter"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        today = date.today()
        q_month = ((today.month - 1) // 3) * 3 + 1
        quarter_start = date(today.year, q_month, 1)
        if q_month + 3 <= 12:
            quarter_end = date(today.year, q_month + 3, 1) - timedelta(days=1)
        else:
            quarter_end = date(today.year + 1, 1, 1) - timedelta(days=1)

        # Find the Bills - Power row
        power_rows = [
            r for r in response.data["rows"] if r["name"] == "Bills - Power"
        ]

        # The RecurringPayment has 3 bills with ~30-day intervals,
        # so next_due_date should exist. If it falls within the quarter
        # and is after today, we expect upcoming_bills to be populated.
        ndd = self.recurring.next_due_date()
        if ndd is not None:
            if hasattr(ndd, "date"):
                ndd = ndd.date()
            if quarter_start <= ndd <= quarter_end and ndd > today:
                self.assertEqual(len(power_rows), 1)
                upcoming = power_rows[0]["upcoming_bills"]
                self.assertGreater(len(upcoming), 0)
                bill = upcoming[0]
                self.assertEqual(bill["name"], "Electricity")
                self.assertIn("expected_date", bill)
                self.assertIn("expected_amount", bill)
