"""Serializers for the recurring-payment / bills API."""
from rest_framework import serializers

from ctrack.models import Bill, RecurringPayment


class BillSerializer(serializers.ModelSerializer):
    is_paid = serializers.ReadOnlyField()

    class Meta:
        model = Bill
        fields = ('url', 'id', 'description', 'due_date', 'due_amount', 'fixed_amount', 'var_amount',
                  'document', 'series', 'paying_transactions', 'is_paid')


class RecurringPaymentSerializer(serializers.ModelSerializer):
    bills = BillSerializer(many=True, read_only=True)

    class Meta:
        model = RecurringPayment
        fields = ('url', 'id', 'name', 'is_income', 'bills', 'next_due_date', 'category')
