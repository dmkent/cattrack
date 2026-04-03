"""ctrack REST API
"""
import logging

from ctrack.api.data_serializer import LoadDataSerializer
from ctrack.api.serializers.recurring_detection import (
    CreateFromDetectionSerializer,
    DetectRecurringRequestSerializer,
    DetectRecurringResponseSerializer,
)
from django.db import transaction as db_transaction
from ctrack.models import (Bill, RecurringPayment, Transaction)
from ctrack.recurring_detection import RecurringTransactionDetector
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
        fields = ('url', 'id', 'name', 'is_income', 'bills', 'next_due_date', 'category')


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

    @decorators.action(detail=False, methods=["post"])
    def detect_recurring(self, request):
        """Detect recurring transaction patterns using clustering."""
        serializer = DetectRecurringRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from_date = serializer.validated_data['from_date']
        to_date = serializer.validated_data['to_date']

        qs = Transaction.objects.filter(
            when__gte=from_date, when__lte=to_date,
            is_split=False, description__isnull=False
        ).exclude(description='')

        if 'account' in serializer.validated_data:
            qs = qs.filter(account=serializer.validated_data['account'])

        if qs.count() < 20:
            return response.Response(
                {"status": "error", "detail": "Need at least 20 transactions with descriptions."},
                status=status.HTTP_400_BAD_REQUEST
            )

        detector = RecurringTransactionDetector(
            min_cluster_size=serializer.validated_data.get('min_cluster_size', 3),
            interval_cv_threshold=serializer.validated_data.get('interval_cv_threshold', 0.35),
            cosine_distance_threshold=serializer.validated_data.get('cosine_distance_threshold', 0.4),
        )
        groups = detector.detect(qs)

        result = {
            "status": "ok",
            "total_transactions": qs.count(),
            "groups_found": len(groups),
            "groups": groups,
        }
        return response.Response(DetectRecurringResponseSerializer(result).data)

    @decorators.action(detail=False, methods=["post"])
    def create_from_detection(self, request):
        """Create RecurringPayment + Bill objects from detected groups."""
        serializer = CreateFromDetectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate all transaction IDs upfront before creating anything
        for group_data in serializer.validated_data['groups']:
            tx_ids = group_data['transaction_ids']
            found_count = Transaction.objects.filter(id__in=tx_ids).count()
            if found_count != len(tx_ids):
                found_ids = set(Transaction.objects.filter(id__in=tx_ids).values_list('id', flat=True))
                missing = set(tx_ids) - found_ids
                return response.Response(
                    {"detail": f"Transaction IDs not found: {sorted(missing)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        created_payments = []
        with db_transaction.atomic():
            for group_data in serializer.validated_data['groups']:
                tx_ids = group_data['transaction_ids']
                transactions = Transaction.objects.filter(id__in=tx_ids).order_by('when')

                payment = RecurringPayment.objects.create(
                    name=group_data['name'],
                    is_income=group_data.get('is_income', False),
                    category=group_data.get('category'),
                )

                for txn in transactions:
                    # Bill.description has max_length=100; truncate if needed
                    desc = (txn.description or payment.name)[:100]
                    bill = Bill.objects.create(
                        description=desc,
                        due_date=txn.when.date(),
                        due_amount=abs(txn.amount),
                        series=payment,
                    )
                    bill.paying_transactions.add(txn)

                created_payments.append(payment)

        result = RecurringPaymentSerializer(
            created_payments, many=True, context={'request': request}
        )
        return response.Response(result.data, status=status.HTTP_201_CREATED)


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.all().order_by('-due_date')
    serializer_class = BillSerializer
    filter_backends = (filters.backends.DjangoFilterBackend,)
    filter_fields = ('due_date', 'series')
