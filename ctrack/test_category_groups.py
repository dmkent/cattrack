"""Tests for CategoryGroup model and API endpoints."""

from datetime import datetime
from django.test import TestCase
import pytz
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from ctrack import models


class CategoryGroupModelTestCase(TestCase):
    """Test CategoryGroup model functionality."""

    def setUp(self):
        """Create test categories."""
        self.cat1 = models.Category.objects.create(name="Groceries")
        self.cat2 = models.Category.objects.create(name="Dining")
        self.cat3 = models.Category.objects.create(name="Transport")

    def test_create_category_group(self):
        """Test creating a category group."""
        group = models.CategoryGroup.objects.create(name="Food & Dining")
        self.assertEqual(group.name, "Food & Dining")
        self.assertEqual(group.categories.count(), 0)

    def test_add_categories_to_group(self):
        """Test adding categories to a group."""
        group = models.CategoryGroup.objects.create(name="Food & Dining")
        group.categories.add(self.cat1, self.cat2)
        self.assertEqual(group.categories.count(), 2)
        self.assertIn(self.cat1, group.categories.all())
        self.assertIn(self.cat2, group.categories.all())

    def test_category_group_string_representation(self):
        """Test string representation of category group."""
        group = models.CategoryGroup.objects.create(name="Food & Dining")
        self.assertEqual(str(group), "Food & Dining")

    def test_category_can_belong_to_multiple_groups(self):
        """Test that a category can belong to multiple groups."""
        group1 = models.CategoryGroup.objects.create(name="Food & Dining")
        group2 = models.CategoryGroup.objects.create(name="Essential Spending")

        group1.categories.add(self.cat1)
        group2.categories.add(self.cat1)

        self.assertIn(self.cat1, group1.categories.all())
        self.assertIn(self.cat1, group2.categories.all())
        self.assertEqual(self.cat1.category_groups.count(), 2)

    def test_category_group_ordering(self):
        """Test that category groups are ordered by name."""
        models.CategoryGroup.objects.create(name="Zebra")
        models.CategoryGroup.objects.create(name="Apple")
        models.CategoryGroup.objects.create(name="Mango")

        groups = models.CategoryGroup.objects.all()
        self.assertEqual(groups[0].name, "Apple")
        self.assertEqual(groups[1].name, "Mango")
        self.assertEqual(groups[2].name, "Zebra")


class CategoryGroupAPITestCase(APITestCase):
    """Test CategoryGroup REST API endpoints."""

    def setUp(self):
        """Create test data and authenticate."""
        # Create user for authentication
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        # Create test categories
        self.cat1 = models.Category.objects.create(name="Groceries")
        self.cat2 = models.Category.objects.create(name="Dining")
        self.cat3 = models.Category.objects.create(name="Transport")

        # Create test account
        self.account = models.Account.objects.create(name="Test Account")

    def test_list_category_groups(self):
        """Test listing category groups."""
        models.CategoryGroup.objects.create(name="Food & Dining")
        models.CategoryGroup.objects.create(name="Transport")

        response = self.client.get("/api/category-groups/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_create_category_group(self):
        """Test creating a category group."""
        data = {"name": "Food & Dining"}
        response = self.client.post("/api/category-groups/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(models.CategoryGroup.objects.count(), 1)
        self.assertEqual(models.CategoryGroup.objects.first().name, "Food & Dining")

    def test_retrieve_category_group(self):
        """Test retrieving a specific category group."""
        group = models.CategoryGroup.objects.create(name="Food & Dining")
        group.categories.add(self.cat1, self.cat2)

        response = self.client.get(f"/api/category-groups/{group.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Food & Dining")
        self.assertEqual(len(response.data["categories"]), 2)

    def test_update_category_group(self):
        """Test updating a category group."""
        group = models.CategoryGroup.objects.create(name="Food & Dining")

        data = {"name": "Food & Entertainment"}
        response = self.client.put(
            f"/api/category-groups/{group.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group.refresh_from_db()
        self.assertEqual(group.name, "Food & Entertainment")

    def test_delete_category_group(self):
        """Test deleting a category group."""
        group = models.CategoryGroup.objects.create(name="Food & Dining")

        response = self.client.delete(f"/api/category-groups/{group.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(models.CategoryGroup.objects.count(), 0)

    def test_weekly_summary_empty_group(self):
        """Test weekly summary with no categories returns empty series."""
        group = models.CategoryGroup.objects.create(name="Empty Group")

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "2026-01-01", "to_date": "2026-01-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_weekly_summary_missing_from_date(self):
        """Test weekly summary without from_date parameter returns error."""
        group = models.CategoryGroup.objects.create(name="Test Group")

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"to_date": "2026-01-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("from_date", response.data["error"])

    def test_weekly_summary_missing_to_date(self):
        """Test weekly summary without to_date parameter returns error."""
        group = models.CategoryGroup.objects.create(name="Test Group")

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "2026-01-01"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to_date", response.data["error"])

    def test_weekly_summary_invalid_date_format(self):
        """Test weekly summary with invalid date format returns error."""
        group = models.CategoryGroup.objects.create(name="Test Group")

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "invalid-date", "to_date": "2026-01-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("format", response.data["error"])

    def test_weekly_summary_no_transactions(self):
        """Test weekly summary with no transactions returns empty series."""
        group = models.CategoryGroup.objects.create(name="Test Group")
        group.categories.add(self.cat1, self.cat2)

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "2026-01-01", "to_date": "2026-01-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_weekly_summary_with_transactions(self):
        """Test weekly summary aggregates transactions correctly."""
        group = models.CategoryGroup.objects.create(name="Test Group")
        group.categories.add(self.cat1, self.cat2)

        # Create transactions across different weeks
        # Week 1: Jan 1-7, 2026 (Wednesday Jan 1)
        models.Transaction.objects.create(
            when=datetime(2026, 1, 1, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=50.00,
            category=self.cat1,
            description="Transaction 1",
        )
        models.Transaction.objects.create(
            when=datetime(2026, 1, 3, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=30.00,
            category=self.cat2,
            description="Transaction 2",
        )

        # Week 2: Jan 8-14, 2026 (Wednesday Jan 8)
        models.Transaction.objects.create(
            when=datetime(2026, 1, 10, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=75.00,
            category=self.cat1,
            description="Transaction 3",
        )

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "2026-01-01", "to_date": "2026-01-15"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)

        # Verify structure of response
        for item in response.data:
            self.assertIn("label", item)
            self.assertIn("value", item)

    def test_weekly_summary_wednesday_start(self):
        """Test that weeks start on Wednesday."""
        group = models.CategoryGroup.objects.create(name="Test Group")
        group.categories.add(self.cat1)

        # Create transaction on Tuesday Jan 7, 2026 (end of week)
        models.Transaction.objects.create(
            when=datetime(2026, 1, 7, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=100.00,
            category=self.cat1,
            description="Tuesday transaction",
        )

        # Create transaction on Wednesday Jan 8, 2026 (start of new week)
        models.Transaction.objects.create(
            when=datetime(2026, 1, 8, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=200.00,
            category=self.cat1,
            description="Wednesday transaction",
        )

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "2026-01-01", "to_date": "2026-01-31"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify that we have exactly 2 weekly buckets
        self.assertEqual(len(response.data), 2)

        # With W-WED resampling (week ending Wednesday):
        # - Tuesday Jan 7 falls into week ending Wed Jan 7
        # - Wednesday Jan 8 falls into week ending Wed Jan 14

        # First bucket: week ending Wednesday Jan 7
        first_bucket = response.data[0]
        self.assertEqual(first_bucket["label"], "2026-01-07T00:00:00Z")
        self.assertEqual(float(first_bucket["value"]), 100.00)

        # Second bucket: week ending Wednesday Jan 14
        second_bucket = response.data[1]
        self.assertEqual(second_bucket["label"], "2026-01-14T00:00:00Z")
        self.assertEqual(float(second_bucket["value"]), 200.00)

    def test_weekly_summary_excludes_other_categories(self):
        """Test that weekly summary only includes transactions from grouped categories."""
        group = models.CategoryGroup.objects.create(name="Test Group")
        group.categories.add(self.cat1)  # Only cat1 in group

        # Transaction in group
        models.Transaction.objects.create(
            when=datetime(2026, 1, 5, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=50.00,
            category=self.cat1,
            description="In group",
        )

        # Transaction not in group
        models.Transaction.objects.create(
            when=datetime(2026, 1, 5, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=100.00,
            category=self.cat3,  # Not in group
            description="Not in group",
        )

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "2026-01-01", "to_date": "2026-01-31"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The total should only include cat1 transactions (50.00)
        # There should be at least one week with data
        if len(response.data) > 0:
            total = sum(float(item["value"]) for item in response.data)
            self.assertEqual(total, 50.00)

    def test_weekly_summary_excludes_split_transactions(self):
        """Test that weekly summary excludes split transactions."""
        group = models.CategoryGroup.objects.create(name="Test Group")
        group.categories.add(self.cat1)

        # Regular transaction
        models.Transaction.objects.create(
            when=datetime(2026, 1, 5, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=50.00,
            category=self.cat1,
            is_split=False,
            description="Regular",
        )

        # Split transaction
        models.Transaction.objects.create(
            when=datetime(2026, 1, 5, 12, 0, tzinfo=pytz.utc),
            account=self.account,
            amount=100.00,
            category=self.cat1,
            is_split=True,
            description="Split",
        )

        response = self.client.get(
            f"/api/category-groups/{group.id}/weekly_summary/",
            {"from_date": "2026-01-01", "to_date": "2026-01-31"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Total should only include non-split transaction
        if len(response.data) > 0:
            total = sum(float(item["value"]) for item in response.data)
            self.assertEqual(total, 50.00)
