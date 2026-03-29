"""
Test UserSettings API endpoint
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from ctrack.models import UserSettings, CategorisorModel


class UserSettingsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        # Create UserSettings for the user
        self.settings = UserSettings.objects.create(user=self.user)
        
    def test_get_user_settings_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = self.client.get('/api/user-settings/')
        # Should get 403 FORBIDDEN (not 401) due to DRF permission checks
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        
    def test_get_user_settings_authenticated(self):
        """Test that authenticated users can retrieve their settings"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/user-settings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return a single object (dict), not a list
        self.assertIsInstance(response.data, dict)
        self.assertIn('selected_categorisor', response.data)
        
    def test_get_user_settings_returns_only_own_settings(self):
        """Test that users only get their own settings"""
        user2 = User.objects.create_user(username='testuser2', password='testpass')
        UserSettings.objects.create(user=user2)
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/user-settings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return single object with id matching self.settings
        self.assertEqual(response.data['id'], self.settings.id)
        
    def test_patch_user_settings(self):
        """Test that users can update their settings"""
        self.client.force_authenticate(user=self.user)
        
        # Get the current settings ID from list endpoint
        get_response = self.client.get('/api/user-settings/')
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        settings_id = get_response.data['id']
        
        # Patch the settings via detail endpoint using JSON format
        patch_data = {'selected_categorisor': None}
        patch_response = self.client.patch(
            f'/api/user-settings/{settings_id}/', 
            patch_data,
            format='json'
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(patch_response.data['selected_categorisor'])

