"""cattrack URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from rest_framework import routers, serializers, viewsets, pagination, filters
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

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'transactions', TransactionViewSet)

urlpatterns = [
    url(r'^api/', include(router.urls)),
    url(r'^admin/', admin.site.urls),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]
