"""ctrack REST API
"""
import logging

from ctrack.api.data_serializer import LoadDataSerializer
from ctrack.models import (Bill, RecurringPayment)
from django_filters import rest_framework as filters
from rest_framework import (decorators, response,
                            serializers, status, viewsets)

logger = logging.getLogger(__name__)


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
        fields = ('url', 'id', 'name', 'is_income', 'bills', 'next_due_date')


class RecurringPaymentViewSet(viewsets.ModelViewSet):
    queryset = RecurringPayment.objects.all().order_by('name')
    serializer_class = RecurringPaymentSerializer

    @decorators.action(detail=True, methods=["post"])
    def loadpdf(self, request, pk=None):
        payments = self.get_object()
        serializer = LoadDataSerializer(data=request.data)
        if serializer.is_valid():
            try:
                payments.add_bill_from_file(serializer.validated_data['data_file'])
            except (ValueError, IOError, TypeError):
                logger.exception("Unable to load PDF")
                return response.Response("Unable to load file. Bad format?",
                                         status=status.HTTP_400_BAD_REQUEST)
            return response.Response({'status': 'loaded'})
        else:
            return response.Response(serializer.errors,
                                     status=status.HTTP_400_BAD_REQUEST)


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.all().order_by('-due_date')
    serializer_class = BillSerializer
    filter_backends = (filters.backends.DjangoFilterBackend,)
    filter_fields = ('due_date', 'series')
