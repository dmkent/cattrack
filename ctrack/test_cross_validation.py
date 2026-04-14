"""Tests for cross-validation API endpoints."""

from datetime import datetime
import pytz
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from ctrack import models


class CrossValidationAPITestCase(APITestCase):
    """Test cross-validation REST API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.categories = {
            "Shopping": models.Category.objects.create(name="Shopping"),
            "Transport": models.Category.objects.create(name="Transport"),
            "Food": models.Category.objects.create(name="Food"),
        }
        self.account = models.Account.objects.create(name="Test Account")

        # Create 30 transactions to exceed the minimum of 20
        descriptions = [
            ("Woolworths", "Shopping"),
            ("Coles", "Shopping"),
            ("Kmart", "Shopping"),
            ("Target", "Shopping"),
            ("Big W", "Shopping"),
            ("Aldi Supermarket", "Shopping"),
            ("Myer Shopping", "Shopping"),
            ("David Jones Shopping", "Shopping"),
            ("Bus Ticket", "Transport"),
            ("Train Pass", "Transport"),
            ("Uber Ride", "Transport"),
            ("Taxi Fare", "Transport"),
            ("Ferry Ticket", "Transport"),
            ("Tram Pass", "Transport"),
            ("Airport Bus", "Transport"),
            ("Rail Pass", "Transport"),
            ("McDonalds Food", "Food"),
            ("KFC Chicken Food", "Food"),
            ("Pizza Hut Food", "Food"),
            ("Subway Food", "Food"),
            ("Sushi Train Food", "Food"),
            ("Thai Restaurant Food", "Food"),
            ("Chinese Food Restaurant", "Food"),
            ("Indian Food Restaurant", "Food"),
            ("Woolworths Groceries", "Shopping"),
            ("Bus Monthly", "Transport"),
            ("Burger King Food", "Food"),
            ("Aldi Store", "Shopping"),
            ("Train Single", "Transport"),
            ("Noodle Bar Food", "Food"),
        ]
        for i, (desc, cat_name) in enumerate(descriptions):
            models.Transaction.objects.create(
                when=datetime(2026, 1, 1 + i, 12, 0, tzinfo=pytz.utc),
                account=self.account,
                amount=10.00 + i,
                category=self.categories[cat_name],
                description=desc,
            )

    def test_cross_validate_returns_results(self):
        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "split_ratio": 0.5,
            "random_seed": 42,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "ok")
        self.assertIn("accuracy", resp.data)
        self.assertIn("matched", resp.data)
        self.assertIn("count", resp.data)
        self.assertIn("failed", resp.data)
        self.assertIn("category_metrics", resp.data)
        self.assertEqual(resp.data["random_seed"], 42)
        self.assertEqual(resp.data["calibration_size"] + resp.data["validation_size"], 30)

    def test_cross_validate_deterministic_with_seed(self):
        """Same seed produces the same split and results."""
        params = {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "split_ratio": 0.5,
            "random_seed": 123,
        }
        resp1 = self.client.post("/api/categorisor/cross_validate/", params)
        resp2 = self.client.post("/api/categorisor/cross_validate/", params)
        self.assertEqual(resp1.data["matched"], resp2.data["matched"])
        self.assertEqual(resp1.data["count"], resp2.data["count"])
        self.assertEqual(resp1.data["accuracy"], resp2.data["accuracy"])

    def test_cross_validate_insufficient_transactions(self):
        """Returns error status when fewer than 20 transactions in period."""
        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-06-01",
            "to_date": "2026-06-30",
            "split_ratio": 0.5,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("Insufficient", resp.data["message"])

    def test_cross_validate_default_split_ratio(self):
        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "ok")
        self.assertEqual(resp.data["split_ratio"], 0.5)

    def test_cross_validate_generates_seed_when_omitted(self):
        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("random_seed", resp.data)
        self.assertIsInstance(resp.data["random_seed"], int)

    def test_cross_validate_invalid_implementation(self):
        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "implementation": "NonExistentClassifier",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unknown implementation", resp.data["error"])

    def test_cross_validate_extreme_split_ratio(self):
        """Extreme split ratios (0.1, 0.9) still produce valid results."""
        for ratio in [0.1, 0.9]:
            resp = self.client.post("/api/categorisor/cross_validate/", {
                "from_date": "2026-01-01",
                "to_date": "2026-01-31",
                "split_ratio": ratio,
                "random_seed": 42,
            })
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertEqual(resp.data["status"], "ok")
            self.assertGreater(resp.data["calibration_size"], 0)
            self.assertGreater(resp.data["validation_size"], 0)

    def test_cross_validate_category_metrics(self):
        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "split_ratio": 0.5,
            "random_seed": 42,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        metrics = resp.data["category_metrics"]
        self.assertIsInstance(metrics, list)
        for metric in metrics:
            self.assertIn("category_name", metric)
            self.assertIn("correct", metric)
            self.assertIn("total", metric)
            self.assertIn("precision", metric)
            self.assertGreaterEqual(metric["precision"], 0.0)
            self.assertLessEqual(metric["precision"], 1.0)

    def test_cross_validate_accepts_enhanced_parameters(self):
        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "split_ratio": 0.5,
            "random_seed": 42,
            "implementation": "EnhancedSklearnCategoriser",
            "threshold": 0.55,
            "margin": 0.10,
            "min_df": 1,
            "max_df": 1.0,
            "alpha": 0.001,
            "calibration_cv": 3,
            "min_category_samples": 3,
        })

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "ok")
        self.assertIn("auto_precision", resp.data)
        self.assertIn("coverage", resp.data)
        self.assertIn("review_count", resp.data)
        self.assertIn("excluded_categories", resp.data)

    def test_cross_validate_excludes_sparse_categories(self):
        rare = models.Category.objects.create(name="Rare")
        for day in (29, 30):
            models.Transaction.objects.create(
                when=datetime(2026, 1, day, 12, 0, tzinfo=pytz.utc),
                account=self.account,
                amount=99.0,
                category=rare,
                description=f"Rare expense {day}",
            )

        resp = self.client.post("/api/categorisor/cross_validate/", {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "split_ratio": 0.5,
            "random_seed": 42,
            "implementation": "EnhancedSklearnCategoriser",
            "min_category_samples": 3,
            "calibration_cv": 3,
        })

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["included_transaction_count"], 30)
        self.assertEqual(resp.data["included_category_count"], 3)
        self.assertEqual(resp.data["excluded_categories"], [{"category_name": "Rare", "count": 2}])

    def test_cross_validate_comparison_mode_is_deterministic(self):
        params = {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "split_ratio": 0.5,
            "random_seed": 123,
            "implementation": "EnhancedSklearnCategoriser",
            "compare_against_baseline": True,
            "calibration_cv": 3,
        }

        resp1 = self.client.post("/api/categorisor/cross_validate/", params)
        resp2 = self.client.post("/api/categorisor/cross_validate/", params)

        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data["comparison"], resp2.data["comparison"])


class CrossValidateSaveAPITestCase(APITestCase):
    """Test cross_validate_save and set_default endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        self.categories = {
            "Shopping": models.Category.objects.create(name="Shopping"),
            "Transport": models.Category.objects.create(name="Transport"),
        }
        self.account = models.Account.objects.create(name="Test Account")

        descriptions = [
            ("Woolworths", "Shopping"),
            ("Coles", "Shopping"),
            ("Kmart", "Shopping"),
            ("Target", "Shopping"),
            ("Big W", "Shopping"),
            ("Aldi", "Shopping"),
            ("Myer", "Shopping"),
            ("David Jones", "Shopping"),
            ("Ikea", "Shopping"),
            ("JB Hifi", "Shopping"),
            ("Bus Ticket", "Transport"),
            ("Train Pass", "Transport"),
            ("Uber Ride", "Transport"),
            ("Taxi Fare", "Transport"),
            ("Ferry Ticket", "Transport"),
            ("Tram Pass", "Transport"),
            ("Airport Bus", "Transport"),
            ("Rail Pass", "Transport"),
            ("Metro Card", "Transport"),
            ("Opal Card", "Transport"),
        ]
        for i, (desc, cat_name) in enumerate(descriptions):
            models.Transaction.objects.create(
                when=datetime(2026, 1, 1 + i, 12, 0, tzinfo=pytz.utc),
                account=self.account,
                amount=10.00 + i,
                category=self.categories[cat_name],
                description=desc,
            )

    def test_save_with_recalibrate_full(self):
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "test-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "recalibrate_full": True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "test-model")
        self.assertTrue(models.CategorisorModel.objects.filter(name="test-model").exists())

    def test_save_without_recalibrate_full(self):
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "partial-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "recalibrate_full": False,
            "split_ratio": 0.6,
            "random_seed": 42,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "partial-model")

    def test_save_without_recalibrate_requires_seed(self):
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "bad-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "recalibrate_full": False,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("required", resp.data["error"])

    def test_save_without_recalibrate_missing_only_seed(self):
        """Error message names only the missing field when one is provided."""
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "bad-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "recalibrate_full": False,
            "split_ratio": 0.5,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("random_seed", resp.data["error"])
        self.assertNotIn("split_ratio", resp.data["error"])

    def test_save_invalid_implementation(self):
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "bad-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "implementation": "FakeClassifier",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unknown implementation", resp.data["error"])

    def test_save_recalibrate_full_empty_period(self):
        """Returns 400 when recalibrate_full but no transactions in period."""
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "empty-model",
            "from_date": "2027-01-01",
            "to_date": "2027-12-31",
            "recalibrate_full": True,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No categorised transactions", resp.data["error"])

    def test_save_with_set_as_default(self):
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "default-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "recalibrate_full": True,
            "set_as_default": True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        settings = models.UserSettings.objects.get(user=self.user)
        self.assertEqual(settings.selected_categorisor.name, "default-model")
        self.assertTrue(settings.enable_db_categorisors)

    def test_set_default_action(self):
        # First create a model
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "my-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "recalibrate_full": True,
        })
        model_id = resp.data["id"]

        # Set it as default
        resp = self.client.post(f"/api/categorisor/{model_id}/set_default/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["detail"], "Model set as default.")

        settings = models.UserSettings.objects.get(user=self.user)
        self.assertEqual(settings.selected_categorisor_id, model_id)
        self.assertTrue(settings.enable_db_categorisors)

    def test_save_enhanced_model_persists_training_metadata(self):
        resp = self.client.post("/api/categorisor/cross_validate_save/", {
            "name": "enhanced-model",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "recalibrate_full": False,
            "split_ratio": 0.6,
            "random_seed": 42,
            "implementation": "EnhancedSklearnCategoriser",
            "threshold": 0.55,
            "margin": 0.10,
            "calibration_cv": 3,
            "min_category_samples": 2,
        })

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        model = models.CategorisorModel.objects.get(name="enhanced-model")
        self.assertEqual(model.training_config["implementation"], "EnhancedSklearnCategoriser")
        self.assertEqual(model.training_config["threshold"], 0.55)
        self.assertEqual(model.training_metrics["split_ratio"], 0.6)
        self.assertEqual(model.training_metrics["random_seed"], 42)
        self.assertIn("coverage", model.training_metrics)
        self.assertIn("excluded_categories", model.exclusion_summary)
