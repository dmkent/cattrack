"""ctrack REST API
"""
from django.conf.urls import include
from django.urls import re_path
from rest_framework import routers
from ctrack.api.accounts import AccountViewSet
from ctrack.api.budget_entry import BudgetEntryViewSet
from ctrack.api.categories import CategorySummary, CategoryTotals, CategoryViewSet, SuggestCategories
from ctrack.api.category_groups import CategoryGroupViewSet
from ctrack.api.categorisor import CategorisorViewSet
from ctrack.api.period_definition import PeriodDefinitionView
from ctrack.api.recurring_payment import BillViewSet, RecurringPaymentViewSet
from ctrack.api.transactions import TransactionViewSet


router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'category-groups', CategoryGroupViewSet)
router.register(r'categorisor', CategorisorViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'payments', RecurringPaymentViewSet)
router.register(r'bills', BillViewSet)
router.register(r'budget', BudgetEntryViewSet)
urls = [
    re_path(r'^transactions/(?P<pk>[0-9]+)/suggest$', SuggestCategories.as_view()),
    re_path(r'^categories/summary/(?P<from>[0-9]+)/(?P<to>[0-9]+)$', CategorySummary.as_view()),
    re_path(r'^categories/totals/(?P<from>[0-9-]+)/(?P<to>[0-9-]+)$', CategoryTotals.as_view()),
    re_path(r'^periods/$', PeriodDefinitionView.as_view()),
    re_path(r'^', include(router.urls)),
]
