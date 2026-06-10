"""Serializers for the accounts API."""
from rest_framework import serializers

from ctrack.models import Account


class AccountSerializer(serializers.HyperlinkedModelSerializer):
    last_transaction = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Account
        fields = ('url', 'id', 'name', 'balance', 'last_transaction')
