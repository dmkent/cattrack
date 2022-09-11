"""ctrack REST API
"""
import logging

from rest_framework import (response, serializers, views)
from ctrack.models import PeriodDefinition


logger = logging.getLogger(__name__)


class PeriodDefinitionSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=40)
    from_date = serializers.DateField()
    to_date = serializers.DateField()

    id = serializers.IntegerField()
    offset = serializers.IntegerField()


class PeriodDefinitionView(views.APIView):
    queryset = PeriodDefinition.objects.all()

    def get(self, formats=None):
        data = sum((period.option_specifiers
                    for period in PeriodDefinition.objects.all()), [])
        return response.Response(data)
