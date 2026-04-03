"""Tests for RecurringTransactionDetector class."""

import random
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.test import TestCase

from ctrack import models
from ctrack.recurring_detection import RecurringTransactionDetector


class RecurringTransactionDetectorTestCase(TestCase):
    """Test RecurringTransactionDetector clustering and frequency detection."""

    def setUp(self):
        """Create test account, categories, and base date."""
        self.account = models.Account.objects.create(name="Test Account")
        self.cat_telco = models.Category.objects.create(name="Telecommunications")
        self.cat_groceries = models.Category.objects.create(name="Groceries")
        self.cat_entertainment = models.Category.objects.create(name="Entertainment")
        self.cat_coffee = models.Category.objects.create(name="Coffee")

        self.base_date = datetime(2025, 1, 1, 12, 0, tzinfo=pytz.utc)
        self.detector = RecurringTransactionDetector(min_cluster_size=3)

    def _create_transactions(self, description, amount_func, interval_days,
                             count, category=None, start_date=None):
        """Helper to create a series of transactions at regular intervals.

        Args:
            description: Transaction description string.
            amount_func: Callable returning a Decimal amount for each transaction.
            interval_days: Days between transactions.
            count: Number of transactions to create.
            category: Optional category FK.
            start_date: Optional start datetime (defaults to self.base_date).

        Returns:
            List of created Transaction objects.
        """
        start = start_date or self.base_date
        txns = []
        for i in range(count):
            txn = models.Transaction.objects.create(
                when=start + timedelta(days=i * interval_days),
                account=self.account,
                amount=amount_func(),
                description=description,
                category=category,
            )
            txns.append(txn)
        return txns

    def test_detect_monthly_fixed(self):
        """Monthly fixed-amount transactions should be detected as monthly/fixed."""
        self._create_transactions(
            description="Vodafone Payment",
            amount_func=lambda: Decimal("-50.00"),
            interval_days=30,
            count=12,
            category=self.cat_telco,
        )

        qs = models.Transaction.objects.filter(
            is_split=False, description__isnull=False
        ).exclude(description="")
        groups = self.detector.detect(qs)

        self.assertGreaterEqual(len(groups), 1)
        vodafone_group = next(
            (g for g in groups if "Vodafone" in g["description_pattern"]), None
        )
        self.assertIsNotNone(vodafone_group, "Vodafone group not detected")
        self.assertEqual(vodafone_group["frequency"], "monthly")
        self.assertEqual(vodafone_group["amount_type"], "fixed")
        self.assertEqual(vodafone_group["transaction_count"], 12)
        self.assertFalse(vodafone_group["is_income"])

    def test_detect_weekly_variable(self):
        """Weekly variable-amount transactions should be detected as weekly/variable."""
        rng = random.Random(42)

        self._create_transactions(
            description="Woolworths Supermarket",
            amount_func=lambda: Decimal(str(round(-80 + rng.gauss(0, 12), 2))),
            interval_days=7,
            count=26,
            category=self.cat_groceries,
        )

        qs = models.Transaction.objects.filter(
            is_split=False, description__isnull=False
        ).exclude(description="")
        groups = self.detector.detect(qs)

        self.assertGreaterEqual(len(groups), 1)
        woolworths_group = next(
            (g for g in groups if "Woolworths" in g["description_pattern"]), None
        )
        self.assertIsNotNone(woolworths_group, "Woolworths group not detected")
        self.assertEqual(woolworths_group["frequency"], "weekly")
        self.assertIn(woolworths_group["amount_type"], ("variable_low", "variable_high"))
        self.assertEqual(woolworths_group["transaction_count"], 26)

    def test_noise_not_detected(self):
        """Random unique transactions should not form any recurring groups."""
        rng = random.Random(99)
        for i in range(35):
            models.Transaction.objects.create(
                when=self.base_date + timedelta(days=rng.randint(0, 365)),
                account=self.account,
                amount=Decimal(str(round(rng.uniform(-200, -5), 2))),
                description=f"RandomMerchant{i} Purchase {rng.randint(1000, 9999)}",
                category=self.cat_groceries,
            )

        qs = models.Transaction.objects.filter(
            is_split=False, description__isnull=False
        ).exclude(description="")
        groups = self.detector.detect(qs)

        self.assertEqual(len(groups), 0)

    def test_mixed_patterns(self):
        """Both monthly and weekly patterns should be detected; noise excluded."""
        # Monthly: Netflix
        self._create_transactions(
            description="Netflix Subscription",
            amount_func=lambda: Decimal("-15.99"),
            interval_days=30,
            count=12,
            category=self.cat_entertainment,
        )

        # Weekly: Coffee Shop
        self._create_transactions(
            description="Coffee Shop Daily Brew",
            amount_func=lambda: Decimal("-5.50"),
            interval_days=7,
            count=26,
            category=self.cat_coffee,
            start_date=self.base_date + timedelta(hours=3),  # offset to avoid collisions
        )

        # Noise: random unique transactions
        rng = random.Random(77)
        for i in range(20):
            models.Transaction.objects.create(
                when=self.base_date + timedelta(days=rng.randint(0, 365)),
                account=self.account,
                amount=Decimal(str(round(rng.uniform(-300, -10), 2))),
                description=f"UniqueMerchant{i} Ref{rng.randint(10000, 99999)}",
                category=None,
            )

        qs = models.Transaction.objects.filter(
            is_split=False, description__isnull=False
        ).exclude(description="")
        groups = self.detector.detect(qs)

        # Should detect at least the two recurring patterns
        self.assertGreaterEqual(len(groups), 2)

        netflix_group = next(
            (g for g in groups if "Netflix" in g["description_pattern"]), None
        )
        coffee_group = next(
            (g for g in groups if "Coffee" in g["description_pattern"]), None
        )
        self.assertIsNotNone(netflix_group, "Netflix group not detected")
        self.assertIsNotNone(coffee_group, "Coffee group not detected")

        self.assertEqual(netflix_group["frequency"], "monthly")
        self.assertEqual(coffee_group["frequency"], "weekly")

        # Verify noise transactions are not included in any group
        all_detected_ids = set()
        for g in groups:
            all_detected_ids.update(g["transaction_ids"])

        noise_txns = models.Transaction.objects.filter(
            description__startswith="UniqueMerchant"
        )
        for txn in noise_txns:
            self.assertNotIn(txn.id, all_detected_ids)

    def test_empty_queryset(self):
        """An empty queryset should return an empty list."""
        qs = models.Transaction.objects.none()
        groups = self.detector.detect(qs)
        self.assertEqual(groups, [])

    def test_insufficient_transactions(self):
        """Fewer transactions than min_cluster_size should return empty list."""
        # Create only 2 transactions (min_cluster_size defaults to 3)
        self._create_transactions(
            description="Vodafone Payment",
            amount_func=lambda: Decimal("-50.00"),
            interval_days=30,
            count=2,
        )

        qs = models.Transaction.objects.filter(
            is_split=False, description__isnull=False
        ).exclude(description="")
        groups = self.detector.detect(qs)

        self.assertEqual(groups, [])

    def test_interleaved_amount_series(self):
        """Two payment series with the same description but different amounts
        should be detected as separate recurring groups.

        This models the real-world case where a gym bills two memberships
        with the same payee description but different amounts on the same dates.
        """
        desc = "EZI*Kieser Training Ge South Melbour"
        base = self.base_date

        # Series A: ~$113 fortnightly
        for i in range(12):
            models.Transaction.objects.create(
                when=base + timedelta(days=i * 14),
                account=self.account,
                amount=Decimal("-113.07"),
                description=desc,
                category=self.cat_entertainment,
            )

        # Series B: ~$100 fortnightly, same dates
        for i in range(12):
            models.Transaction.objects.create(
                when=base + timedelta(days=i * 14),
                account=self.account,
                amount=Decimal("-100.20"),
                description=desc,
                category=self.cat_entertainment,
            )

        qs = models.Transaction.objects.filter(
            is_split=False, description__isnull=False
        ).exclude(description="")
        groups = self.detector.detect(qs)

        # Should detect two separate groups, not one mixed group
        self.assertGreaterEqual(len(groups), 2,
            f"Expected 2+ groups but got {len(groups)}: "
            f"{[(g['amount_mean'], g['transaction_count']) for g in groups]}"
        )

        # Verify the groups have distinct amount ranges
        amount_means = sorted([abs(g['amount_mean']) for g in groups])
        self.assertGreater(amount_means[-1] - amount_means[0], 5.0,
            "Groups should have meaningfully different mean amounts"
        )

        # Each group should be regular (fortnightly)
        for g in groups:
            self.assertEqual(g['frequency'], 'fortnightly',
                f"Group with mean {g['amount_mean']} has frequency {g['frequency']}"
            )
