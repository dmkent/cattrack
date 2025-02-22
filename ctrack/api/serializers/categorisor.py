"""ctrack REST API
"""
from rest_framework import serializers
from ctrack.api.transactions import TransactionSerializer
from ctrack.models import CategorisorModel

class CategorisorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CategorisorModel
        fields = ('url', 'id', 'name', 'implementation', 'from_date', 'to_date')

class ValidateSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()

class CreateCategorisor(serializers.Serializer):
    name = serializers.CharField()
    implementation = serializers.CharField()
    from_date = serializers.DateTimeField()
    to_date = serializers.DateTimeField()

class SuggestionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    score = serializers.FloatField()

class FailedMatchSerializer(serializers.Serializer):
    transaction = TransactionSerializer()
    modelled = SuggestionSerializer()
    
class ValidationResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    matched = serializers.IntegerField()
    failed = serializers.ListField(
        child=FailedMatchSerializer()
    )
