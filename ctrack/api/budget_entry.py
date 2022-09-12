"""ctrack REST API
"""
import logging

from rest_framework import serializers, viewsets
from ctrack.models import BudgetEntry


logger = logging.getLogger(__name__)

class BudgetEntrySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BudgetEntry
        fields = ('url', 'id', 'pretty_name', 'amount', 'valid_from', 'valid_to', 'categories')

class BudgetEntryViewSet(viewsets.ModelViewSet):
    queryset = BudgetEntry.objects.all()
    serializer_class = BudgetEntrySerializer
