"""Progress tracking API — shows actual vs budget vs expected spend."""

import logging
from datetime import date

from rest_framework import response, views

from ctrack.api.serializers.progress import ProgressResponseSerializer
from ctrack.services import progress_service

logger = logging.getLogger(__name__)


class ProgressView(views.APIView):
    """GET /api/progress/ — progress tracking for a given period."""

    def get(self, request, format=None):
        today = date.today()

        from_date, to_date, label = progress_service.resolve_period(
            request.query_params, today
        )
        if from_date is None:
            return response.Response(
                {"detail": "Provide 'period' or both 'from_date' and 'to_date'."},
                status=400,
            )

        group_by = request.query_params.get("group_by", "category")

        data = progress_service.compute_progress(
            from_date, to_date, label, group_by, today=today
        )

        serializer = ProgressResponseSerializer(data)
        return response.Response(serializer.data)
