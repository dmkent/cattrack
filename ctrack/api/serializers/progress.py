"""Serializers for the progress-tracking API."""
from rest_framework import serializers


class ProgressPeriodSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    label = serializers.CharField()


class UpcomingBillSerializer(serializers.Serializer):
    name = serializers.CharField()
    expected_date = serializers.DateField()
    expected_amount = serializers.DecimalField(max_digits=8, decimal_places=2)


class ProgressRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    actual_spend = serializers.DecimalField(max_digits=20, decimal_places=2)
    expected_remaining = serializers.DecimalField(max_digits=20, decimal_places=2)
    budget = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)
    upcoming_bills = UpcomingBillSerializer(many=True)


class ProgressTotalsSerializer(serializers.Serializer):
    actual_spend = serializers.DecimalField(max_digits=20, decimal_places=2)
    expected_remaining = serializers.DecimalField(max_digits=20, decimal_places=2)
    budget = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)


class ProgressResponseSerializer(serializers.Serializer):
    period = ProgressPeriodSerializer()
    rows = ProgressRowSerializer(many=True)
    totals = ProgressTotalsSerializer()
