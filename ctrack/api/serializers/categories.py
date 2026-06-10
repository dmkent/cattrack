"""Serializers for the categories API."""
from rest_framework import serializers

from ctrack.models import Category


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Category
        fields = ('url', 'id', 'name')


class ScoredCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=50)
    score = serializers.IntegerField()


class CategorySummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=50)
    value = serializers.FloatField()
    budget = serializers.FloatField()
