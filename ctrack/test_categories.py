from django.test import TestCase
import pandas as pd

from ctrack import categories


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
