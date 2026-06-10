"""Serializers for the transactions API."""
from rest_framework import serializers

from ctrack.models import Category, Transaction


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Transaction
        fields = ('url', 'id', 'when', 'amount', 'description', 'category', 'category_name', 'account')


class SplitTransSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class SummarySerializer(serializers.Serializer):
    category = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField(max_length=100, source='category__name', allow_null=True)
    subcategory = serializers.SerializerMethodField()
    total = serializers.DecimalField(max_digits=20, decimal_places=2)

    def get_subcategory(self, obj):
        return Category.subcategory_prefix_from_name(obj.get('category__name'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('category_name') is None:
            data['category_name'] = "None"
        if data.get('subcategory') is None:
            data['subcategory'] = "None"
        return data
