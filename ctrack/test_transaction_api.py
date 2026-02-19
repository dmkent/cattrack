"""Tests for Transaction API endpoints."""

from datetime import datetime
import pytz
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from ctrack import models


class TransactionAPITestCase(APITestCase):
    """Test Transaction REST API endpoints."""

    def setUp(self):
        """Create test data and authenticate."""
        # Create user for authentication
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        # Create test categories
        self.cat1 = models.Category.objects.create(name="Food - Groceries")
        self.cat2 = models.Category.objects.create(name="Transport")

        # Create test account
        self.account = models.Account.objects.create(name="Test Account")

        # Create test transactions with various descriptions
        models.Transaction.objects.create(
            when=datetime(2026, 1, 1, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=50.00,
            category=self.cat1,
            description="Woolworths Supermarket",
        )
        models.Transaction.objects.create(
            when=datetime(2026, 1, 2, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=30.00,
            category=self.cat2,
            description="Bus Ticket",
        )
        models.Transaction.objects.create(
            when=datetime(2026, 1, 3, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=75.00,
            category=self.cat1,
            description="Coles Supermarket",
        )
        models.Transaction.objects.create(
            when=datetime(2026, 1, 4, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=100.00,
            category=self.cat2,
            description="Train Monthly Pass",
        )

    def test_search_by_description_case_insensitive(self):
        """Test searching transactions by description (case insensitive)."""
        response = self.client.get("/api/transactions/", {"description": "supermarket"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        descriptions = [item["description"] for item in response.data["results"]]
        self.assertIn("Woolworths Supermarket", descriptions)
        self.assertIn("Coles Supermarket", descriptions)

    def test_search_by_description_partial_match(self):
        """Test searching transactions by partial description."""
        response = self.client.get("/api/transactions/", {"description": "bus"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["description"], "Bus Ticket")

    def test_search_by_description_no_match(self):
        """Test searching transactions with no matching description."""
        response = self.client.get("/api/transactions/", {"description": "restaurant"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_search_by_description_combined_with_date_filter(self):
        """Test combining description search with date filters."""
        response = self.client.get(
            "/api/transactions/",
            {"description": "supermarket", "from_date": "2026-01-02"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["description"], "Coles Supermarket"
        )

    def test_search_by_description_combined_with_category_filter(self):
        """Test combining description search with category filter."""
        response = self.client.get(
            "/api/transactions/", {"description": "ticket", "category": self.cat2.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["description"], "Bus Ticket")

    def test_list_transactions_without_description_filter(self):
        """Test that listing transactions without description filter returns all."""
        response = self.client.get("/api/transactions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 4)

    def test_summary_returns_subcategory_values(self):
        """Summary endpoint includes computed subcategory field."""
        response = self.client.get("/api/transactions/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = {item["category_name"]: item for item in response.data}
        self.assertIn("Food - Groceries", summary)
        self.assertIn("Transport", summary)
        self.assertEqual(summary["Food - Groceries"]["subcategory"], "Food")
        self.assertEqual(summary["Transport"]["subcategory"], "Transport")

    def test_summary_normalizes_null_category_name(self):
        """Summary response converts null category names to literal 'None'."""
        models.Transaction.objects.create(
            when=datetime(2026, 1, 5, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=25.00,
            category=None,
            description="Uncategorised",
        )

        response = self.client.get("/api/transactions/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        uncategorised = next(item for item in response.data if item["category"] is None)
        self.assertEqual(uncategorised["category_name"], "None")
        self.assertEqual(uncategorised["subcategory"], "None")
