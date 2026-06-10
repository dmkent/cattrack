"""Serializers for the budget-entry API."""
from rest_framework import serializers

from ctrack.models import BudgetEntry


class BudgetEntrySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BudgetEntry
        fields = ('url', 'id', 'pretty_name', 'amount', 'valid_from', 'valid_to', 'categories')
