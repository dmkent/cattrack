"""ctrack REST API - UserSettings ViewSet
"""
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ctrack.models import UserSettings
from ctrack.api.serializers.user_settings import UserSettingsSerializer


class UserSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's settings."""
        # Get or create the settings for the current user
        obj, created = UserSettings.objects.get_or_create(user=self.request.user)
        return UserSettings.objects.filter(user=self.request.user)

    def get_object(self):
        """Get or create the settings object for the current user."""
        obj, created = UserSettings.objects.get_or_create(user=self.request.user)
        return obj

    def list(self, request, *args, **kwargs):
        """Override list to return a single object for the current user."""
        # Ensure the user has a settings object
        obj, created = UserSettings.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

