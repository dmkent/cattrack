"""Query-count regression tests for Phase 2 performance fixes.

These guard against the N+1 patterns removed in Phase 2: ``suggest_category``
building a per-prediction ``Category`` lookup, the transaction list endpoint
issuing a category query per row, and the recurring-payments/bills list
endpoints issuing an ``is_paid`` aggregate per nested bill.
"""

from datetime import date, datetime

import pytz
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from ctrack import models


class FakeClassifier:
    """Minimal stand-in for a Categoriser: returns a fixed {name: score} dict."""

    def __init__(self, predictions):
        self._predictions = predictions

    def predict(self, description):
        return self._predictions


class SuggestCategoryQueryTests(TestCase):
    def setUp(self):
        self.account = models.Account.objects.create(name="Test Account")
        self.food = models.Category.objects.create(name="Food")
        self.transport = models.Category.objects.create(name="Transport")
        self.trans = models.Transaction.objects.create(
            when=datetime(2026, 1, 1, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=10,
            description="something",
        )

    def test_single_query_regardless_of_prediction_count(self):
        """Without a map, exactly one query runs no matter how many labels."""
        clf = FakeClassifier({"Food": 0.9, "Transport": 0.1})
        with self.assertNumQueries(1):
            result = self.trans.suggest_category(clf)
        self.assertEqual([r["name"] for r in result], ["Food", "Transport"])
        self.assertEqual(result[0]["id"], self.food.id)

    def test_no_queries_when_map_supplied(self):
        """A precomputed category_map removes all per-call queries."""
        clf = FakeClassifier({"Food": 0.9, "Transport": 0.1})
        category_map = {c.name: c.id for c in models.Category.objects.all()}
        with self.assertNumQueries(0):
            result = self.trans.suggest_category(clf, category_map=category_map)
        self.assertEqual(len(result), 2)

    def test_unknown_label_is_skipped(self):
        """Predicted labels with no matching Category are dropped, not errored."""
        clf = FakeClassifier({"Food": 0.5, "DoesNotExist": 0.5})
        result = self.trans.suggest_category(clf)
        self.assertEqual([r["name"] for r in result], ["Food"])


class TransactionListQueryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_authenticate(user=self.user)
        self.account = models.Account.objects.create(name="Acct")
        self.category = models.Category.objects.create(name="Food - Groceries")

    def _create_transactions(self, count):
        for i in range(count):
            models.Transaction.objects.create(
                when=datetime(2026, 1, 1, 12, 0, tzinfo=pytz.utc),
                account=self.account,
                amount=10 + i,
                category=self.category,
                description=f"txn {i}",
            )

    def test_list_query_count_does_not_grow_with_rows(self):
        """select_related('category') keeps the list endpoint query count flat."""
        self._create_transactions(3)
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.client.get("/api/transactions/").status_code, 200)

        self._create_transactions(7)  # 10 total
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.client.get("/api/transactions/").status_code, 200)

        self.assertEqual(len(small.captured_queries), len(large.captured_queries))


class RecurringPaymentListQueryTests(APITestCase):
    """The serialized Bill.is_paid must not issue a query per nested bill."""

    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.client.force_authenticate(user=self.user)
        self.account = models.Account.objects.create(name="Acct")
        self.payment = models.RecurringPayment.objects.create(name="Rent")

    def _add_bills(self, count):
        for i in range(count):
            bill = models.Bill.objects.create(
                description=f"bill {i}",
                due_date=date(2026, 1, 1),
                due_amount=10,
                series=self.payment,
            )
            txn = models.Transaction.objects.create(
                when=datetime(2026, 1, 1, 12, 0, tzinfo=pytz.utc),
                account=self.account,
                amount=-10,
                description=f"payment {i}",
            )
            bill.paying_transactions.add(txn)

    def test_payments_list_query_count_flat_in_bill_count(self):
        self._add_bills(2)
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.client.get("/api/payments/").status_code, 200)

        self._add_bills(6)  # 8 bills total on the payment
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.client.get("/api/payments/").status_code, 200)

        self.assertEqual(len(small.captured_queries), len(large.captured_queries))

    def test_bills_list_query_count_flat_in_bill_count(self):
        self._add_bills(2)
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.client.get("/api/bills/").status_code, 200)

        self._add_bills(6)
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.client.get("/api/bills/").status_code, 200)

        self.assertEqual(len(small.captured_queries), len(large.captured_queries))
