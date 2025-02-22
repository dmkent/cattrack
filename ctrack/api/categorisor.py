"""ctrack REST API
"""
from datetime import datetime, time
import logging

from django.utils import timezone
from rest_framework import decorators, status, response, viewsets
from ctrack.api.serializers.categorisor import CategorisorSerializer, CreateCategorisor, ValidateSerializer, ValidationResponseSerializer
from ctrack.categories import CategoriserFactory
from ctrack.models import CategorisorModel, Transaction


logger = logging.getLogger(__name__)


class CategorisorViewSet(viewsets.ModelViewSet):
    queryset = CategorisorModel.objects.all().order_by('name')
    serializer_class = CategorisorSerializer

    def create(self, request):
        serializer = CreateCategorisor(data=request.data)

        if serializer.is_valid():
            transactions = Transaction.objects.filter(
                when__gte=serializer.validated_data['from_date'],
                when__lte=serializer.validated_data['to_date'],
                category__isnull=False
            )

            try:
                bin_data = self.calibrate(
                    serializer.validated_data['from_date'],
                    serializer.validated_data['to_date'],
                    serializer.validated_data['implementation']
                )
            except Exception:
                return response.Response({'error': 'Unknown implementation: '},
                    status=status.HTTP_400_BAD_REQUEST)

            record = CategorisorModel.objects.create(
                name=serializer.validated_data['name'],
                implementation=serializer.validated_data['implementation'],
                from_date=serializer.validated_data['from_date'],
                to_date=serializer.validated_data['to_date'],
                model=bin_data
            )

            return response.Response(CategorisorSerializer(record, context={'request': request}).data)
        else:
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def calibrate(self, from_date, to_date, implementation):
            transactions = Transaction.objects.filter(
                when__gte=from_date,
                when__lte=to_date,
                category__isnull=False
            )

            cls = CategoriserFactory.get_by_name(implementation)

            categorisor = cls()
            categorisor.fit_queryset(transactions)

            return categorisor.to_bytes()
    
    @decorators.action(detail=True, methods=["get", "post"])
    def recalibrate(self, request, pk=None):
        details = self.get_object()
        bin_data = self.calibrate(details.from_date, details.to_date, details.implementation)
        details.model = bin_data
        details.save()

        return response.Response("ok")

    @decorators.action(detail=True, methods=["get"], serializer_class=ValidateSerializer)
    def validate(self, request, pk=None):
        categorisor = self.get_object()
        serializer = self.get_serializer(data=request.query_params)

        serializer.is_valid(raise_exception=True)

        from_date = datetime.combine(serializer.validated_data['from_date'], time(), timezone.get_current_timezone())
        to_date = datetime.combine(serializer.validated_data['to_date'], time(), timezone.get_current_timezone())

        transactions = Transaction.objects.filter(
                when__gte=from_date,
                when__lte=to_date,
            )
        clf = categorisor.clf_model()

        count = 0
        matched = 0
        failed = []
        for trans in transactions:
            if trans.category:
                suggested = trans.suggest_category(clf)
                count += 1
                if suggested[0]['id'] == trans.category.id:
                    matched += 1
                else:
                    failed += [{
                        "transaction": trans,
                        "modelled": suggested[0]
                    }]

        responseSerializer = ValidationResponseSerializer(
            {"count": count, "matched": matched, "failed": failed},
            context={'request': request}
        )
        return response.Response(responseSerializer.data)
