"""ctrack REST API - UserSettings ViewSet
"""
from rest_framework import viewsets, mixins
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ctrack.models import UserSettings
from ctrack.api.serializers.user_settings import UserSettingsSerializer


class UserSettingsViewSet(mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin,
                          viewsets.GenericViewSet):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's settings."""
        return UserSettings.objects.filter(user=self.request.user)

    def get_object(self):
        """Get or create the settings object for the current user.

        Also validates that any pk provided in the URL matches the
        current user's settings, returning 404 if it does not.
        """
        obj, created = UserSettings.objects.get_or_create(user=self.request.user)
        self.check_object_permissions(self.request, obj)
        pk = self.kwargs.get('pk')
        if pk is not None and str(obj.pk) != str(pk):
            raise NotFound()
        return obj

    def list(self, request, *args, **kwargs):
        """Return the current user's settings as a single object."""
        obj, created = UserSettings.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)
