from datetime import datetime

import pytz
from django.test import TestCase
import pandas as pd

from ctrack import categories, models


class SklCategoriserTests(TestCase):
    def setUp(self):
        self.categoriser = categories.SklearnCategoriser()
        self.categoriser._fit_impl([
            ["Shopping", "Shopping"],
            ["Transport first", "Transport"],
            ["Transport again", "Transport"],
            ["Groceries", "Shopping"],
            ["House", "House"],
            ["Training", "Training"],
            ["Transport/Car", "Car"],
            ["School", "School"],
            ["Childcare", "School"],
        ])

    def test_predict(self):
        predictions = self.categoriser.predict('Shopping')
        self.assertEqual(predictions.index[0], 'Shopping')

        predictions = self.categoriser.predict('Transport')
        self.assertEqual(predictions.index[0], 'Transport')

        predictions = self.categoriser.predict('X')
        self.assertEqual(predictions.index[0], 'School')


class EnhancedSklearnCategoriserTests(TestCase):
    def test_predict_details_accepts_high_confidence_predictions(self):
        categoriser = categories.EnhancedSklearnCategoriser(threshold=0.6, margin=0.15)
        categoriser._predict_scores = lambda text: pd.Series(
            [0.72, 0.18, 0.10],
            index=['Travel', 'Food', 'Shopping'],
        )

        details = categoriser.predict_details('airport transfer')

        self.assertTrue(details['accepted'])
        self.assertEqual(details['gated_prediction'], 'Travel')
        self.assertEqual(list(details['suggestions'].index), ['Travel'])

    def test_predict_details_routes_low_confidence_predictions_to_review(self):
        categoriser = categories.EnhancedSklearnCategoriser(threshold=0.6, margin=0.15)
        categoriser._predict_scores = lambda text: pd.Series(
            [0.58, 0.46, 0.12],
            index=['Travel', 'Food', 'Shopping'],
        )

        details = categoriser.predict_details('ambiguous payment')

        self.assertFalse(details['accepted'])
        self.assertIsNone(details['gated_prediction'])
        self.assertEqual(list(details['suggestions'].index), ['Travel', 'Food'])


class PrepareQuerysetExclusionTests(TestCase):
    def setUp(self):
        self.account = models.Account.objects.create(name="Test Account")
        self.categories = {
            name: models.Category.objects.create(name=name)
            for name in ("Shopping", "Transport", "Food")
        }
        # Shopping: 6, Transport: 4, Food: 2 transactions.
        rows = (
            [("Shopping", "Shopping")] * 6
            + [("Transport", "Transport")] * 4
            + [("Food", "Food")] * 2
        )
        for i, (desc, cat_name) in enumerate(rows):
            models.Transaction.objects.create(
                when=datetime(2026, 1, 1 + i, 12, 0, tzinfo=pytz.utc),
                account=self.account,
                amount=10.00 + i,
                category=self.categories[cat_name],
                description=desc,
            )

    def test_excludes_categories_below_calibration_cv_when_higher(self):
        """When calibration_cv > min_category_samples, the larger threshold wins
        and the exclusion summary reflects exactly what is trained."""
        prepared = categories.EnhancedSklearnCategoriser.prepare_queryset(
            models.Transaction.objects.all(),
            min_category_samples=2,
            calibration_cv=5,
        )

        excluded = {item['category_name'] for item in prepared['excluded_categories']}
        self.assertEqual(excluded, {"Transport", "Food"})
        self.assertEqual(prepared['included_category_count'], 1)
        self.assertEqual(prepared['included_transaction_count'], 6)

        trained_categories = set(
            prepared['queryset'].values_list('category__name', flat=True)
        )
        self.assertEqual(trained_categories, {"Shopping"})

    def test_uses_min_category_samples_when_higher(self):
        prepared = categories.EnhancedSklearnCategoriser.prepare_queryset(
            models.Transaction.objects.all(),
            min_category_samples=5,
            calibration_cv=3,
        )

        excluded = {item['category_name'] for item in prepared['excluded_categories']}
        self.assertEqual(excluded, {"Transport", "Food"})
        self.assertEqual(prepared['included_category_count'], 1)
