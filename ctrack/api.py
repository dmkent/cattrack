"""ctrack REST API
"""
from django.conf.urls import url, include
from django.http import Http404, HttpResponseBadRequest
from rest_framework import filters, generics, pagination, response, routers, serializers, views, viewsets
import django_filters
from ctrack.models import Account, Category, Transaction

# Serializers define the API representation.
class AccountSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Account
        fields = ('url', 'id', 'name')

class CategorySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Category
        fields = ('url', 'id', 'name')

class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Transaction
        fields = ('url', 'id', 'when', 'amount', 'description', 'category', 'category_name', 'account')

# ViewSets define the view behavior.
class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer

class PageNumberSettablePagination(pagination.PageNumberPagination):
    page_size_query_param = 'page_size'
    page_size = 100

class DateRangeTransactionFilter(filters.FilterSet):
    from_date = django_filters.DateFilter(name='when', lookup_expr='gte')
    to_date = django_filters.DateFilter(name='when', lookup_expr='lte')
    class Meta:
        model = Transaction
        fields = ('from_date', 'to_date', 'account', 'category',)

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    pagination_class = PageNumberSettablePagination
    filter_class = DateRangeTransactionFilter


class SuggestCategories(generics.ListAPIView):
    """
        Suggest categories for a transaction.
    """
    serializer_class = CategorySerializer

    def get_queryset(self):
        try:
            transaction = Transaction.objects.get(pk=self.kwargs['pk'])
        except Transaction.DoesNotExist:
            raise Http404
        return Category.objects.filter(name__in=transaction.suggest_category())


class SplitTransSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class SplitTransactionView(views.APIView):
    """
        Split a transaction.
    """
    queryset = Transaction.objects.all()

    def post(self, request, pk, format=None):
        try:
            transaction = Transaction.objects.get(pk=pk)
        except Transaction.DoesNotExist:
            raise Http404
        args = {}
        for elem in request.data:
            serializer = SplitTransSerializer(data=elem)
            if serializer.is_valid():
                args[serializer.validated_data['category']] = serializer.validated_data['amount']
            else:
                return HttpResponseBadRequest("Invalid arguments.")
        transaction.split(args)
        return {}

router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'transactions', TransactionViewSet)
urls = [
    url(r'^transactions/(?P<pk>[0-9]+)/suggest$', SuggestCategories.as_view()),
    url(r'^transactions/(?P<pk>[0-9]+)/split$', SplitTransactionView.as_view()),
    url(r'^', include(router.urls)),
]
