"""ctrack REST API
"""
import logging

from rest_framework import viewsets
from ctrack.api.serializers.budget_entry import BudgetEntrySerializer
from ctrack.models import BudgetEntry


logger = logging.getLogger(__name__)

class BudgetEntryViewSet(viewsets.ModelViewSet):
    queryset = BudgetEntry.objects.all()
    serializer_class = BudgetEntrySerializer
