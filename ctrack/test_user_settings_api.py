"""
Test UserSettings API endpoint
"""

from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from ctrack.models import UserSettings


class UserSettingsAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        # Create UserSettings for the user
        self.settings = UserSettings.objects.create(user=self.user)

    def test_get_user_settings_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = self.client.get("/api/user-settings/me/")
        # Should get either 401 UNAUTHORIZED or 403 FORBIDDEN due to DRF authentication/permission checks
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_get_user_settings_authenticated(self):
        """Test that authenticated users can retrieve their settings"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/user-settings/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return a single object (dict), not a list
        self.assertIsInstance(response.data, dict)
        self.assertIn("selected_categorisor", response.data)

    def test_get_user_settings_returns_only_own_settings(self):
        """Test that users only get their own settings"""
        user2 = User.objects.create_user(username="testuser2", password="testpass")
        UserSettings.objects.create(user=user2)

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/user-settings/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return single object with id matching self.settings
        self.assertEqual(response.data["id"], self.settings.id)

    def test_patch_user_settings(self):
        """Test that users can update their settings"""
        self.client.force_authenticate(user=self.user)

        # Get current settings via me endpoint
        get_response = self.client.get("/api/user-settings/me/")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)

        # Patch settings via me endpoint using JSON format
        patch_data = {"selected_categorisor": None}
        patch_response = self.client.patch(
            "/api/user-settings/me/", patch_data, format="json"
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(patch_response.data["selected_categorisor"])

    def test_get_user_settings_autocreates(self):
        """Test that GET creates UserSettings if none exists for the user"""
        user_no_settings = User.objects.create_user(
            username="nosettingsuser", password="testpass"
        )
        self.assertFalse(UserSettings.objects.filter(user=user_no_settings).exists())

        self.client.force_authenticate(user=user_no_settings)
        response = self.client.get("/api/user-settings/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
        self.assertIn("selected_categorisor", response.data)
        # Verify it was created in the DB
        self.assertTrue(UserSettings.objects.filter(user=user_no_settings).exists())

    def test_post_not_allowed_on_me(self):
        """Test that POST is not allowed on the me endpoint"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/user-settings/me/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_not_allowed_on_me(self):
        """Test that DELETE is not allowed on the me endpoint"""
        self.client.force_authenticate(user=self.user)
        response = self.client.delete("/api/user-settings/me/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_list_route_exposes_me_link_only(self):
        """Test that /api/user-settings/ is discovery-only and points to /me"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/user-settings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("me", response.data)
        self.assertTrue(response.data["me"].endswith("/api/user-settings/me/"))
