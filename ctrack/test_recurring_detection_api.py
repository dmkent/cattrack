"""API integration tests for RecurringPaymentViewSet detection endpoints."""

import random
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from ctrack import models


class RecurringDetectionAPITestCase(APITestCase):
    """Test detect_recurring and create_from_detection API endpoints."""

    def setUp(self):
        """Create user, authenticate, and set up test data."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.account1 = models.Account.objects.create(name="Account One")
        self.account2 = models.Account.objects.create(name="Account Two")
        self.cat_telco = models.Category.objects.create(name="Telecommunications")
        self.cat_groceries = models.Category.objects.create(name="Groceries")

        self.base_date = datetime(2025, 1, 1, 12, 0, tzinfo=pytz.utc)

    def _create_recurring_transactions(self, description, amount, interval_days,
                                       count, account=None, category=None,
                                       start_date=None):
        """Helper to create a series of recurring transactions."""
        account = account or self.account1
        start = start_date or self.base_date
        txns = []
        for i in range(count):
            txn = models.Transaction.objects.create(
                when=start + timedelta(days=i * interval_days),
                account=account,
                amount=amount,
                description=description,
                category=category,
            )
            txns.append(txn)
        return txns

    def _create_noise_transactions(self, count, account=None, start_date=None):
        """Create random noise transactions that should not cluster."""
        rng = random.Random(123)
        account = account or self.account1
        start = start_date or self.base_date
        for i in range(count):
            models.Transaction.objects.create(
                when=start + timedelta(days=rng.randint(0, 365)),
                account=account,
                amount=Decimal(str(round(rng.uniform(-200, -5), 2))),
                description=f"RandomPlace{i} TxRef{rng.randint(10000, 99999)}",
                category=None,
            )

    def _populate_sufficient_data(self, account=None):
        """Create enough data for detection: recurring + noise to reach 20+ txns."""
        account = account or self.account1
        self._create_recurring_transactions(
            description="Vodafone Monthly Bill",
            amount=Decimal("-50.00"),
            interval_days=30,
            count=12,
            account=account,
            category=self.cat_telco,
        )
        self._create_noise_transactions(count=15, account=account)

    def test_detect_recurring_endpoint(self):
        """POST detect_recurring with sufficient data returns groups_found > 0."""
        self._populate_sufficient_data()

        response = self.client.post(
            "/api/payments/detect_recurring/",
            {
                "from_date": "2025-01-01",
                "to_date": "2026-02-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertGreater(response.data["groups_found"], 0)
        self.assertGreater(response.data["total_transactions"], 0)
        self.assertIsInstance(response.data["groups"], list)

    def test_detect_recurring_insufficient_data(self):
        """POST detect_recurring with < 20 transactions returns 400."""
        # Create only a handful of transactions
        self._create_recurring_transactions(
            description="Vodafone Monthly Bill",
            amount=Decimal("-50.00"),
            interval_days=30,
            count=5,
        )

        response = self.client.post(
            "/api/payments/detect_recurring/",
            {
                "from_date": "2025-01-01",
                "to_date": "2025-06-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_detect_recurring_with_account_filter(self):
        """Account filter restricts analysis to that account's transactions only."""
        # Populate account1 with recurring + noise (enough for detection)
        self._populate_sufficient_data(account=self.account1)

        # Populate account2 with only noise (not enough recurring)
        self._create_noise_transactions(count=25, account=self.account2)

        # Detect for account1 -- should find the Vodafone pattern
        response1 = self.client.post(
            "/api/payments/detect_recurring/",
            {
                "from_date": "2025-01-01",
                "to_date": "2026-02-01",
                "account": self.account1.pk,
            },
            format="json",
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertGreater(response1.data["groups_found"], 0)

        # Detect for account2 -- should find no recurring patterns
        response2 = self.client.post(
            "/api/payments/detect_recurring/",
            {
                "from_date": "2025-01-01",
                "to_date": "2026-02-01",
                "account": self.account2.pk,
            },
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data["groups_found"], 0)

    def test_create_from_detection(self):
        """POST create_from_detection creates RecurringPayment and linked Bills."""
        txns = self._create_recurring_transactions(
            description="Vodafone Monthly Bill",
            amount=Decimal("-50.00"),
            interval_days=30,
            count=6,
            category=self.cat_telco,
        )
        tx_ids = [t.id for t in txns]

        response = self.client.post(
            "/api/payments/create_from_detection/",
            {
                "groups": [
                    {
                        "name": "Vodafone",
                        "transaction_ids": tx_ids,
                        "is_income": False,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 1)

        # Verify RecurringPayment created
        payment = models.RecurringPayment.objects.get(name="Vodafone")
        self.assertFalse(payment.is_income)

        # Verify Bills created -- one per transaction
        bills = models.Bill.objects.filter(series=payment)
        self.assertEqual(bills.count(), 6)

        # Verify each Bill has a paying_transaction set
        for bill in bills:
            self.assertEqual(bill.paying_transactions.count(), 1)

    def test_create_from_detection_invalid_ids(self):
        """POST create_from_detection with non-existent IDs returns 400."""
        response = self.client.post(
            "/api/payments/create_from_detection/",
            {
                "groups": [
                    {
                        "name": "Ghost Payment",
                        "transaction_ids": [999990, 999991, 999992],
                        "is_income": False,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_create_from_detection_with_category(self):
        """POST create_from_detection with category sets it on RecurringPayment."""
        txns = self._create_recurring_transactions(
            description="Vodafone Monthly Bill",
            amount=Decimal("-50.00"),
            interval_days=30,
            count=4,
            category=self.cat_telco,
        )
        tx_ids = [t.id for t in txns]

        response = self.client.post(
            "/api/payments/create_from_detection/",
            {
                "groups": [
                    {
                        "name": "Vodafone",
                        "transaction_ids": tx_ids,
                        "is_income": False,
                        "category": self.cat_telco.pk,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        payment = models.RecurringPayment.objects.get(name="Vodafone")
        self.assertEqual(payment.category, self.cat_telco)
