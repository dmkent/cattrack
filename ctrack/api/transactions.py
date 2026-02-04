"""ctrack REST API
"""
import logging

from django.db.models import Sum
from django.http import HttpResponseBadRequest
from rest_framework import (decorators, pagination, response,
                            serializers, status, viewsets)
from django_filters import rest_framework as filters
import django_filters
from ctrack.models import (Category, Transaction)


logger = logging.getLogger(__name__)


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Transaction
        fields = ('url', 'id', 'when', 'amount', 'description', 'category', 'category_name', 'account')


class SplitTransSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


# ViewSets define the view behavior.
class PageNumberSettablePagination(pagination.PageNumberPagination):
    page_size_query_param = 'page_size'
    page_size = 100


class SummarySerializer(serializers.Serializer):
    category = serializers.IntegerField()
    category_name = serializers.CharField(max_length=40, source='category__name')
    total = serializers.DecimalField(max_digits=20, decimal_places=2)


class DateRangeTransactionFilter(filters.FilterSet):
    from_date = django_filters.DateFilter(field_name='when', lookup_expr='gte')
    to_date = django_filters.DateFilter(field_name='when', lookup_expr='lte')
    has_category = django_filters.BooleanFilter(
        field_name='category', exclude=True, lookup_expr='isnull',
    )
    description = django_filters.CharFilter(field_name='description', lookup_expr='icontains')
    class Meta:
        model = Transaction
        fields = ('from_date', 'to_date', 'account', 'category', 'has_category', 'description')

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.filter(is_split=False).order_by("-when", "-pk")
    serializer_class = TransactionSerializer
    pagination_class = PageNumberSettablePagination
    filterset_class = DateRangeTransactionFilter

    @decorators.action(detail=True, methods=["post"])
    def split(self, request, pk=None):
        transaction = self.get_object()
        args = {}
        for elem in request.data:
            serializer = SplitTransSerializer(data=elem)
            if serializer.is_valid():
                args[serializer.validated_data['category']] = serializer.validated_data['amount']
            else:
                return HttpResponseBadRequest("Invalid arguments.")
        try:
            transaction.split(args)
        except Exception as thrown:
            return response.Response("Unable to set categories: {}".format(thrown),
                                     status=status.HTTP_400_BAD_REQUEST)
        return response.Response({"message": "Success"})

    @decorators.action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.filter_queryset(self.get_queryset().order_by())
        result = queryset.values('category', 'category__name').annotate(total=Sum('amount')).order_by('total')
        serialised = SummarySerializer(result, many=True)
        return response.Response(serialised.data)
