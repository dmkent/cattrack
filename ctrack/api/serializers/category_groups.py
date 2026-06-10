"""Serializers for the category-groups API."""
from rest_framework import serializers

from ctrack.models import CategoryGroup


class CategoryGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CategoryGroup
        fields = ("url", "id", "name", "categories")
        extra_kwargs = {"categories": {"required": False}}
