"""ctrack REST API
"""
from django.conf.urls import url, include
from django.http import Http404, HttpResponseBadRequest
from rest_framework import (decorators, filters, generics, pagination, response, routers,
                            serializers, status, views, viewsets)
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


class SplitTransSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class LoadDataSerializer(serializers.Serializer):
    data_file = serializers.FileField()

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
    queryset = Transaction.objects.filter(is_split=False).order_by("-when")
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


router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'transactions', TransactionViewSet)
urls = [
    url(r'^transactions/(?P<pk>[0-9]+)/suggest$', SuggestCategories.as_view()),
    url(r'^', include(router.urls)),
]
