"""Category Groups REST API"""

from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import decorators, response, serializers, viewsets
import pandas as pd

from ctrack.models import CategoryGroup, Transaction
from ctrack.api.series_serializer import SeriesSerializer


class CategoryGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CategoryGroup
        fields = ("url", "id", "name", "categories")
        extra_kwargs = {"categories": {"required": False}}


class CategoryGroupViewSet(viewsets.ModelViewSet):
    queryset = CategoryGroup.objects.all().order_by("name")
    serializer_class = CategoryGroupSerializer

    @decorators.action(detail=True, methods=["get"])
    def weekly_summary(self, request, pk=None):
        """
        Get weekly transaction summary for this category group.
        Weeks start on Wednesday.

        Query Parameters:
            from_date: Start date (YYYY-MM-DD format, required)
            to_date: End date (YYYY-MM-DD format, required)

        Returns:
            Time series with weekly totals starting on Wednesdays
        """
        category_group = self.get_object()

        # Validate required parameters
        from_date_str = request.query_params.get("from_date")
        to_date_str = request.query_params.get("to_date")

        if not from_date_str:
            return response.Response(
                {"error": "from_date parameter is required"}, status=400
            )
        if not to_date_str:
            return response.Response(
                {"error": "to_date parameter is required"}, status=400
            )

        # Parse dates
        from_date = parse_date(from_date_str)
        to_date = parse_date(to_date_str)

        if not from_date:
            return response.Response(
                {"error": "from_date must be in YYYY-MM-DD format"}, status=400
            )
        if not to_date:
            return response.Response(
                {"error": "to_date must be in YYYY-MM-DD format"}, status=400
            )

        # Get categories in this group
        categories = category_group.categories.all()

        # Return empty series if no categories
        if not categories.exists():
            serialised = SeriesSerializer([], many=True)
            return response.Response(serialised.data)

        # Build Q object for filtering by multiple categories
        category_filter = Q(category__in=categories)

        # Get transactions for all categories in the group
        transactions = Transaction.objects.filter(
            category_filter, when__gte=from_date, when__lte=to_date, is_split=False
        ).order_by("when")

        # Return empty series if no transactions
        if not transactions.exists():
            serialised = SeriesSerializer([], many=True)
            return response.Response(serialised.data)

        # Convert to pandas DataFrame
        df = pd.DataFrame(
            {
                "when": [t.when for t in transactions],
                "amount": [float(t.amount) for t in transactions],
            }
        )

        # Set when as index
        df.set_index("when", inplace=True)

        # Resample by week starting on Wednesday, sum amounts
        # W-WED means week ending on Wednesday, so we need W-TUE to start on Wednesday
        weekly_series = df["amount"].resample("W-TUE").sum()

        # Convert to format expected by SeriesSerializer
        weekly_series.index.name = "dtime"
        result = weekly_series.to_frame("value").reset_index().to_dict(orient="records")

        serialised = SeriesSerializer(result, many=True)
        return response.Response(serialised.data)
