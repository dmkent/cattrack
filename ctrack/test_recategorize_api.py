"""Tests for re-categorization API endpoints."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytz
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from ctrack import models


def make_mock_classifier(prediction_map):
    """Create a mock classifier that returns predictions based on a mapping.

    Args:
        prediction_map: dict mapping description substrings to
                        {category_name: score} dicts.
    """
    clf = MagicMock()

    def predict(description):
        for substr, scores in prediction_map.items():
            if substr.lower() in description.lower():
                return pd.Series(scores)
        return pd.Series(dtype=float)

    clf.predict = predict
    return clf


class PreviewRecategorizeTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.cat_food = models.Category.objects.create(name="Food")
        self.cat_transport = models.Category.objects.create(name="Transport")
        self.cat_caffeine = models.Category.objects.create(name="Caffeine")

        self.account = models.Account.objects.create(name="Test Account")

        # Transaction where prediction will differ (Food -> Caffeine)
        self.trans_mismatch = models.Transaction.objects.create(
            when=datetime(2026, 1, 15, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=5.00,
            category=self.cat_food,
            description="Coffee Shop",
        )
        # Transaction where prediction will match (Transport -> Transport)
        self.trans_match = models.Transaction.objects.create(
            when=datetime(2026, 1, 16, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=30.00,
            category=self.cat_transport,
            description="Bus Ticket",
        )
        # Uncategorized transaction
        self.trans_uncat = models.Transaction.objects.create(
            when=datetime(2026, 1, 17, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=10.00,
            category=None,
            description="Latte",
        )
        # Split transaction (should be excluded)
        self.trans_split = models.Transaction.objects.create(
            when=datetime(2026, 1, 18, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=100.00,
            category=self.cat_food,
            is_split=True,
            description="Mixed Purchase",
        )
        # Transaction outside date range
        models.Transaction.objects.create(
            when=datetime(2026, 3, 1, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=20.00,
            category=self.cat_food,
            description="Coffee Shop Outside Range",
        )

        self.prediction_map = {
            "coffee": {"Caffeine": 0.9},
            "bus": {"Transport": 0.85},
            "latte": {"Caffeine": 0.8},
            "mixed": {"Food": 0.7},
        }

        self.categorisor = models.CategorisorModel.objects.create(
            name="test",
            implementation="SklearnCategoriser",
            from_date="2025-01-01",
            to_date="2026-12-31",
            model=b"dummy",
        )

        self.url = f"/api/categorisor/{self.categorisor.pk}/preview_recategorize/"

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_returns_only_differing_predictions(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        transaction_ids = [r["transaction"]["id"] for r in response.data["results"]]
        self.assertIn(self.trans_mismatch.pk, transaction_ids)
        self.assertNotIn(self.trans_match.pk, transaction_ids)

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_includes_uncategorized_transactions(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        transaction_ids = [r["transaction"]["id"] for r in response.data["results"]]
        self.assertIn(self.trans_uncat.pk, transaction_ids)

        uncat_result = next(
            r for r in response.data["results"]
            if r["transaction"]["id"] == self.trans_uncat.pk
        )
        self.assertIsNone(uncat_result["current_category"]["id"])
        self.assertIsNone(uncat_result["current_category"]["name"])

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_excludes_matching_predictions(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        transaction_ids = [r["transaction"]["id"] for r in response.data["results"]]
        self.assertNotIn(self.trans_match.pk, transaction_ids)

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_excludes_split_transactions(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        transaction_ids = [r["transaction"]["id"] for r in response.data["results"]]
        self.assertNotIn(self.trans_split.pk, transaction_ids)

    def test_preview_requires_date_params(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_is_paginated(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_response_shape(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result = response.data["results"][0]
        self.assertIn("transaction", result)
        self.assertIn("current_category", result)
        self.assertIn("suggested_category", result)
        self.assertIn("id", result["suggested_category"])
        self.assertIn("name", result["suggested_category"])
        self.assertIn("score", result["suggested_category"])

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_excludes_transactions_outside_date_range(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        descriptions = [
            r["transaction"]["description"] for r in response.data["results"]
        ]
        self.assertNotIn("Coffee Shop Outside Range", descriptions)

    @patch.object(models.CategorisorModel, "clf_model")
    def test_preview_skips_null_description(self, mock_clf):
        mock_clf.return_value = make_mock_classifier(self.prediction_map)

        models.Transaction.objects.create(
            when=datetime(2026, 1, 19, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=15.00,
            category=self.cat_food,
            description=None,
        )

        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should not crash and null-description transaction should not appear
        transaction_ids = [r["transaction"]["id"] for r in response.data["results"]]
        null_desc_trans = models.Transaction.objects.get(description=None)
        self.assertNotIn(null_desc_trans.pk, transaction_ids)

    def test_preview_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            self.url, {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        )
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class ApplyRecategorizeTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.cat_food = models.Category.objects.create(name="Food")
        self.cat_caffeine = models.Category.objects.create(name="Caffeine")

        self.account = models.Account.objects.create(name="Test Account")

        self.trans1 = models.Transaction.objects.create(
            when=datetime(2026, 1, 15, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=5.00,
            category=self.cat_food,
            description="Coffee Shop",
        )
        self.trans2 = models.Transaction.objects.create(
            when=datetime(2026, 1, 16, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=10.00,
            category=self.cat_food,
            description="Latte",
        )
        self.trans3 = models.Transaction.objects.create(
            when=datetime(2026, 1, 17, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=20.00,
            category=self.cat_food,
            description="Groceries",
        )

        self.categorisor = models.CategorisorModel.objects.create(
            name="test",
            implementation="SklearnCategoriser",
            from_date="2025-01-01",
            to_date="2026-12-31",
            model=b"dummy",
        )

        self.url = f"/api/categorisor/{self.categorisor.pk}/apply_recategorize/"

    def test_apply_updates_categories(self):
        response = self.client.post(
            self.url,
            {
                "updates": [
                    {"transaction": self.trans1.pk, "category": self.cat_caffeine.pk},
                    {"transaction": self.trans2.pk, "category": self.cat_caffeine.pk},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 2)

        self.trans1.refresh_from_db()
        self.trans2.refresh_from_db()
        self.assertEqual(self.trans1.category, self.cat_caffeine)
        self.assertEqual(self.trans2.category, self.cat_caffeine)

    def test_apply_partial_accept(self):
        response = self.client.post(
            self.url,
            {
                "updates": [
                    {"transaction": self.trans1.pk, "category": self.cat_caffeine.pk},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 1)

        self.trans1.refresh_from_db()
        self.trans3.refresh_from_db()
        self.assertEqual(self.trans1.category, self.cat_caffeine)
        self.assertEqual(self.trans3.category, self.cat_food)

    def test_apply_empty_updates(self):
        response = self.client.post(
            self.url, {"updates": []}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_invalid_transaction_id(self):
        response = self.client.post(
            self.url,
            {"updates": [{"transaction": 99999, "category": self.cat_caffeine.pk}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_invalid_category_id(self):
        response = self.client.post(
            self.url,
            {"updates": [{"transaction": self.trans1.pk, "category": 99999}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_duplicate_transactions_rejected(self):
        response = self.client.post(
            self.url,
            {
                "updates": [
                    {"transaction": self.trans1.pk, "category": self.cat_caffeine.pk},
                    {"transaction": self.trans1.pk, "category": self.cat_food.pk},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            self.url,
            {
                "updates": [
                    {"transaction": self.trans1.pk, "category": self.cat_caffeine.pk},
                ]
            },
            format="json",
        )
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
