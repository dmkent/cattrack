"""ctrack REST API"""

import logging

from rest_framework import response, views
from ctrack.api.serializers.period_definition import PeriodDefinitionSerializer
from ctrack.models import PeriodDefinition


logger = logging.getLogger(__name__)


class PeriodDefinitionView(views.APIView):
    queryset = PeriodDefinition.objects.all()
    serializer_class = PeriodDefinitionSerializer

    def get(self, formats=None):
        data = sum(
            (period.option_specifiers for period in PeriodDefinition.objects.all()), []
        )
        return response.Response(data)
