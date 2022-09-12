"""ctrack REST API
"""
from django.conf.urls import url, include
from rest_framework import routers
from ctrack.api.accounts import AccountViewSet
from ctrack.api.budget_entry import BudgetEntryViewSet
from ctrack.api.categories import CategorySummary, CategoryViewSet, SuggestCategories
from ctrack.api.categorisor import CategorisorViewSet
from ctrack.api.period_definition import PeriodDefinitionView
from ctrack.api.recurring_payment import BillViewSet, RecurringPaymentViewSet
from ctrack.api.transactions import TransactionViewSet


router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'categorisor', CategorisorViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'payments', RecurringPaymentViewSet)
router.register(r'bills', BillViewSet)
router.register(r'budget', BudgetEntryViewSet)
urls = [
    url(r'^transactions/(?P<pk>[0-9]+)/suggest$', SuggestCategories.as_view()),
    url(r'^categories/summary/(?P<from>[0-9]+)/(?P<to>[0-9]+)$', CategorySummary.as_view()),
    url(r'^periods/$', PeriodDefinitionView.as_view()),
    url(r'^', include(router.urls)),
]
