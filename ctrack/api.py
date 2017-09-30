"""ctrack REST API
"""
from datetime import date

from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.conf.urls import url, include
from django.http import Http404, HttpResponseBadRequest
from rest_framework import (decorators, filters, generics, pagination, response, routers,
                            serializers, status, views, viewsets)
import django_filters
from ctrack.models import Account, Category, Transaction, PeriodDefinition, RecurringPayment, Bill

# Serializers define the API representation.
class AccountSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Account
        fields = ('url', 'id', 'name')


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Category
        fields = ('url', 'id', 'name')


class ScoredCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=50)
    score = serializers.IntegerField()


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Transaction
        fields = ('url', 'id', 'when', 'amount', 'description', 'category', 'category_name', 'account')


class BillSerializer(serializers.ModelSerializer):
    is_paid = serializers.ReadOnlyField()

    class Meta:
        model = Bill
        fields = ('url', 'id', 'description', 'due_date', 'due_amount', 'fixed_amount', 'var_amount',
                  'document', 'series', 'paying_transactions', 'is_paid')


class RecurringPaymentSerializer(serializers.ModelSerializer):
    bills = BillSerializer(many=True, read_only=True)

    class Meta:
        model = RecurringPayment
        fields = ('url', 'id', 'name', 'is_income', 'bills')


class SplitTransSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class LoadDataSerializer(serializers.Serializer):
    data_file = serializers.FileField()


class PeriodDefinitionSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=40)
    from_date = serializers.DateField()
    to_date = serializers.DateField()

    id = serializers.IntegerField()
    offset = serializers.IntegerField()


class SeriesSerializer(serializers.Serializer):
    label = serializers.DateTimeField(source='dtime')
    value = serializers.DecimalField(max_digits=20, decimal_places=2)


class SummarySerializer(serializers.Serializer):
    category = serializers.IntegerField()
    category_name = serializers.CharField(max_length=40, source='category__name')
    total = serializers.DecimalField(max_digits=20, decimal_places=2)


# ViewSets define the view behavior.
class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    @decorators.detail_route(methods=["post"])
    def load(self, request, pk=None):
        account = self.get_object()
        serializer = LoadDataSerializer(data=request.data)
        if serializer.is_valid():
            try:
                account.load_ofx(serializer.validated_data['data_file'])
            except (ValueError, IOError, TypeError):
                return response.Response("Unable to load file. Bad format?",
                                         status=status.HTTP_400_BAD_REQUEST)
            return response.Response({'status': 'loaded'})
        else:
            return response.Response(serializer.errors,
                                     status=status.HTTP_400_BAD_REQUEST)

    @decorators.detail_route(methods=["get"])
    def series(self, request, pk=None):
        series = self.get_object().daily_balance()
        series.index.name = 'dtime'
        serialised = SeriesSerializer(series.to_frame('value').reset_index().to_dict(orient='records'), many=True)
        return response.Response(serialised.data)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer

    @decorators.detail_route(methods=["get"])
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

class PageNumberSettablePagination(pagination.PageNumberPagination):
    page_size_query_param = 'page_size'
    page_size = 100

class DateRangeTransactionFilter(filters.FilterSet):
    from_date = django_filters.DateFilter(name='when', lookup_expr='gte')
    to_date = django_filters.DateFilter(name='when', lookup_expr='lte')
    has_category = django_filters.BooleanFilter(
        name='category', exclude=True, lookup_expr='isnull',
    )
    class Meta:
        model = Transaction
        fields = ('from_date', 'to_date', 'account', 'category', 'has_category')

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.filter(is_split=False).order_by("-when", "-pk")
    serializer_class = TransactionSerializer
    pagination_class = PageNumberSettablePagination
    filter_class = DateRangeTransactionFilter

    @decorators.detail_route(methods=["post"])
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

    @decorators.list_route(methods=["get"])
    def summary(self, request):
        queryset = self.filter_queryset(self.get_queryset().order_by())
        result = queryset.values('category', 'category__name').annotate(total=Sum('amount')).order_by('total')
        serialised = SummarySerializer(result, many=True)
        return response.Response(serialised.data)


class SuggestCategories(generics.ListAPIView):
    """
        Suggest categories for a transaction.
    """
    serializer_class = ScoredCategorySerializer

    def get_queryset(self):
        try:
            transaction = Transaction.objects.get(pk=self.kwargs['pk'])
        except Transaction.DoesNotExist:
            raise Http404
        try:
            return transaction.suggest_category()
        except Category.DoesNotExist:
            raise Http404


class PeriodDefinitionView(views.APIView):
    queryset = PeriodDefinition.objects.all()

    def get(self, formats=None):
        data = sum((period.option_specifiers
                    for period in PeriodDefinition.objects.all()), [])
        return response.Response(data)


class RecurringPaymentViewSet(viewsets.ModelViewSet):
    queryset = RecurringPayment.objects.all().order_by('name')
    serializer_class = RecurringPaymentSerializer


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.all().order_by('-due_date')
    serializer_class = BillSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('due_date', 'series')


router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'payments', RecurringPaymentViewSet)
router.register(r'bills', BillViewSet)
urls = [
    url(r'^transactions/(?P<pk>[0-9]+)/suggest$', SuggestCategories.as_view()),
    url(r'^periods/$', PeriodDefinitionView.as_view()),
    url(r'^', include(router.urls)),
]
