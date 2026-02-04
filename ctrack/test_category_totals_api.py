"""Tests for Category Totals API endpoint."""

from datetime import datetime
import pytz
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from ctrack import models


class CategoryTotalsAPITestCase(APITestCase):
    """Test Category Totals REST API endpoint."""

    def setUp(self):
        """Create test data and authenticate."""
        # Create user for authentication
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        # Create test categories
        self.cat1 = models.Category.objects.create(name="Groceries")
        self.cat2 = models.Category.objects.create(name="Transport")
        self.cat3 = models.Category.objects.create(name="Entertainment")

        # Create test account
        self.account = models.Account.objects.create(name="Test Account")

        # Create test transactions
        # January 2026 transactions
        models.Transaction.objects.create(
            when=datetime(2026, 1, 5, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=50.00,
            category=self.cat1,
            description="Groceries Jan 5",
        )
        models.Transaction.objects.create(
            when=datetime(2026, 1, 10, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=75.00,
            category=self.cat1,
            description="Groceries Jan 10",
        )
        models.Transaction.objects.create(
            when=datetime(2026, 1, 15, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=30.00,
            category=self.cat2,
            description="Transport Jan 15",
        )
        
        # February 2026 transactions
        models.Transaction.objects.create(
            when=datetime(2026, 2, 5, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=100.00,
            category=self.cat2,
            description="Transport Feb 5",
        )
        models.Transaction.objects.create(
            when=datetime(2026, 2, 10, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=25.00,
            category=self.cat3,
            description="Entertainment Feb 10",
        )

    def test_category_totals_for_january(self):
        """Test getting category totals for January 2026."""
        response = self.client.get("/api/categories/totals/2026-01-01/2026-01-31")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return 2 categories (Groceries and Transport)
        self.assertEqual(len(response.data), 2)
        
        # Check the totals
        totals_by_category = {item['category']: item for item in response.data}
        
        self.assertIn(self.cat1.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat1.id]['total']), 125.00)
        self.assertEqual(totals_by_category[self.cat1.id]['category_name'], "Groceries")
        
        self.assertIn(self.cat2.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat2.id]['total']), 30.00)
        self.assertEqual(totals_by_category[self.cat2.id]['category_name'], "Transport")

    def test_category_totals_for_february(self):
        """Test getting category totals for February 2026."""
        response = self.client.get("/api/categories/totals/2026-02-01/2026-02-28")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return 2 categories (Transport and Entertainment)
        self.assertEqual(len(response.data), 2)
        
        # Check the totals
        totals_by_category = {item['category']: item for item in response.data}
        
        self.assertIn(self.cat2.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat2.id]['total']), 100.00)
        
        self.assertIn(self.cat3.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat3.id]['total']), 25.00)

    def test_category_totals_full_range(self):
        """Test getting category totals for full date range."""
        response = self.client.get("/api/categories/totals/2026-01-01/2026-02-28")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return 3 categories
        self.assertEqual(len(response.data), 3)
        
        # Check the totals
        totals_by_category = {item['category']: item for item in response.data}
        
        self.assertIn(self.cat1.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat1.id]['total']), 125.00)
        
        self.assertIn(self.cat2.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat2.id]['total']), 130.00)
        
        self.assertIn(self.cat3.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat3.id]['total']), 25.00)

    def test_category_totals_no_transactions(self):
        """Test getting category totals for date range with no transactions."""
        response = self.client.get("/api/categories/totals/2025-01-01/2025-01-31")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return empty list
        self.assertEqual(len(response.data), 0)

    def test_category_totals_single_day(self):
        """Test getting category totals for a single day."""
        response = self.client.get("/api/categories/totals/2026-01-05/2026-01-05")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should return 1 category
        self.assertEqual(len(response.data), 1)
        
        totals_by_category = {item['category']: item for item in response.data}
        self.assertIn(self.cat1.id, totals_by_category)
        self.assertEqual(float(totals_by_category[self.cat1.id]['total']), 50.00)

    def test_category_totals_excludes_split_transactions(self):
        """Test that split transactions are excluded from totals."""
        # Create a split transaction
        parent = models.Transaction.objects.create(
            when=datetime(2026, 1, 20, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=200.00,
            category=self.cat1,
            description="Split parent",
            is_split=True,
        )
        
        response = self.client.get("/api/categories/totals/2026-01-01/2026-01-31")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # The split transaction should not be included
        totals_by_category = {item['category']: item for item in response.data}
        self.assertEqual(float(totals_by_category[self.cat1.id]['total']), 125.00)
