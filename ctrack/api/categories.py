"""ctrack REST API
"""
import logging

from dateutil.parser import parse as parse_date
from dateutil import relativedelta

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.http import Http404
from rest_framework import (decorators, generics, response,
                            serializers, viewsets)
from ctrack.api.series_serializer import SeriesSerializer
from ctrack.models import (Category, Transaction, BudgetEntry)


logger = logging.getLogger(__name__)


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Category
        fields = ('url', 'id', 'name')


class ScoredCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=50)
    score = serializers.IntegerField()


class CategorySummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=50)
    value = serializers.FloatField()
    budget = serializers.FloatField()


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer

    @decorators.action(detail=True, methods=["get"])
    def series(self, request, pk=None):
        category = self.get_object()
        queryset = category.transaction_set
        result = (queryset
            .annotate(dtime=TruncMonth('when'))
            .values('dtime')
            .annotate(value=Sum('amount'))
        )
        serialised = SeriesSerializer(result, many=True)
        return response.Response(serialised.data)


class SuggestCategories(generics.ListAPIView):
    """
        Suggest categories for a transaction.
    """
    serializer_class = ScoredCategorySerializer

    def get_queryset(self):
        user = self.request.user
        clf = user.usersettings.get_clf_model()
        try:
            transaction = Transaction.objects.get(pk=self.kwargs['pk'])
        except Transaction.DoesNotExist:
            raise Http404
        try:
            return transaction.suggest_category(clf)
        except Category.DoesNotExist:
            raise Http404


class CategorySummary(generics.ListAPIView):
    """
        Summaries for all categories.
    """
    serializer_class = CategorySummarySerializer

    def get_queryset(self):
        from_date = parse_date(self.kwargs["from"])
        to_date = parse_date(self.kwargs["to"])
        filters = {
            "when__gte": from_date,
            "when__lte": to_date,
        }
        result = []
        for budget_entry in BudgetEntry.objects.for_period(to_date).order_by("-amount"):
            transactions = Transaction.objects.filter(category__in=budget_entry.categories.values_list("pk", flat=True), **filters)
            value = 0.0
            if transactions:
                value = float(transactions.aggregate(sum=Sum("amount"))["sum"])

            budget = budget_entry.amount_over_period(from_date, to_date)
            result.append({
                "id": budget_entry.id,
                "name": budget_entry.pretty_name,
                "value": value,
                "budget": budget
            })
        return result


class CategoryTotalsSerializer(serializers.Serializer):
    category = serializers.IntegerField()
    category_name = serializers.CharField(max_length=40, source='category__name')
    total = serializers.DecimalField(max_digits=20, decimal_places=2)


class CategoryTotals(generics.ListAPIView):
    """
    Per-category transaction totals for a given time period.
    
    Returns aggregated transaction amounts grouped by category for the specified
    date range. Split transactions (is_split=True) are excluded to prevent
    double-counting.
    
    URL Parameters:
        from: Start date in YYYY-MM-DD format (inclusive)
        to: End date in YYYY-MM-DD format (inclusive)
    
    Returns:
        List of objects containing:
            - category: Category ID (integer)
            - category_name: Category name (string)
            - total: Sum of transaction amounts for the category (decimal)
    
    Example:
        GET /api/categories/totals/2026-01-01/2026-01-31
    """
    serializer_class = CategoryTotalsSerializer

    def get_queryset(self):
        from_date = parse_date(self.kwargs["from"])
        to_date = parse_date(self.kwargs["to"])
        # Add one day to to_date to include the entire day (use __lt instead of __lte)
        to_date = to_date + relativedelta.relativedelta(days=1)
        filters = {
            "when__gte": from_date,
            "when__lt": to_date,
            "is_split": False,
        }
        result = (Transaction.objects
                  .filter(**filters)
                  .values('category', 'category__name')
                  .annotate(total=Sum('amount'))
                  .order_by('total'))
        return result
