"""Serializers for recurring transaction detection API."""
from rest_framework import serializers

from ctrack.models import Account, Category


class DetectRecurringRequestSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    min_cluster_size = serializers.IntegerField(default=3, min_value=2, max_value=20)
    interval_cv_threshold = serializers.FloatField(default=0.35, min_value=0.1, max_value=1.0)
    similarity_threshold = serializers.FloatField(default=0.4, min_value=0.1, max_value=0.9)
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), required=False
    )


class DetectedGroupSerializer(serializers.Serializer):
    cluster_id = serializers.IntegerField()
    description_pattern = serializers.CharField()
    sample_descriptions = serializers.ListField(child=serializers.CharField())
    frequency = serializers.CharField()
    mean_interval_days = serializers.FloatField()
    interval_cv = serializers.FloatField()
    regularity_score = serializers.FloatField()
    amount_mean = serializers.FloatField()
    amount_std = serializers.FloatField()
    amount_type = serializers.CharField()
    is_income = serializers.BooleanField()
    transaction_count = serializers.IntegerField()
    transaction_ids = serializers.ListField(child=serializers.IntegerField())
    first_date = serializers.DateField()
    last_date = serializers.DateField()
    category = serializers.IntegerField(allow_null=True)
    category_name = serializers.CharField(allow_null=True)


class DetectRecurringResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    total_transactions = serializers.IntegerField()
    groups_found = serializers.IntegerField()
    groups = DetectedGroupSerializer(many=True)


class CreateFromDetectionItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    transaction_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    is_income = serializers.BooleanField(default=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )


class CreateFromDetectionSerializer(serializers.Serializer):
    groups = CreateFromDetectionItemSerializer(many=True, min_length=1)
