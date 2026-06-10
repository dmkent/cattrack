"""Serializers for the period-definition API."""
from rest_framework import serializers


class PeriodDefinitionSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=40)
    from_date = serializers.DateField()
    to_date = serializers.DateField()

    id = serializers.IntegerField()
    offset = serializers.IntegerField()
