"""ctrack REST API - UserSettings ViewSet
"""
from rest_framework import decorators, response, status, viewsets
from rest_framework.permissions import IsAuthenticated
from ctrack.models import UserSettings
from ctrack.api.serializers.user_settings import UserSettingsSerializer


class UserSettingsViewSet(viewsets.GenericViewSet):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """Discovery endpoint for browsable API root.

        Returns a link to the self-scoped settings endpoint.
        """
        return response.Response({'me': self.reverse_action('me')})

    def _get_or_create_settings(self):
        obj, created = UserSettings.objects.get_or_create(user=self.request.user)
        self.check_object_permissions(self.request, obj)
        return obj

    @decorators.action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def me(self, request):
        obj = self._get_or_create_settings()

        if request.method == 'GET':
            serializer = self.get_serializer(obj)
            return response.Response(serializer.data)

        partial = request.method == 'PATCH'
        serializer = self.get_serializer(obj, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(serializer.data, status=status.HTTP_200_OK)
