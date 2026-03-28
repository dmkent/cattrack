"""ctrack REST API
"""
from collections import defaultdict
from datetime import datetime, time
import logging
import random

from django.utils import timezone
from rest_framework import decorators, status, response, viewsets
from ctrack.api.serializers.categorisor import (
    CategorisorSerializer, CreateCategorisor, ValidateSerializer,
    ValidationResponseSerializer, CrossValidateSerializer,
    CrossValidationErrorSerializer, CrossValidationResponseSerializer,
    CrossValidateSaveSerializer,
)
from ctrack.categories import CategoriserFactory
from ctrack.models import CategorisorModel, Transaction, UserSettings


logger = logging.getLogger(__name__)

MIN_CROSS_VALIDATION_TRANSACTIONS = 20


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

    def calibrate(self, from_date, to_date, implementation, queryset=None):
        if queryset is None:
            queryset = Transaction.objects.filter(
                when__gte=from_date,
                when__lte=to_date,
                category__isnull=False
            )

        cls = CategoriserFactory.get_by_name(implementation)

        categorisor = cls()
        categorisor.fit_queryset(queryset)

        return categorisor.to_bytes()

    def _split_transaction_pks(self, from_date, to_date, split_ratio, random_seed=None):
        """Split categorised transactions into calibration and validation sets.

        Returns (calibration_pks, validation_pks, seed) or None if too few transactions.
        """
        pks = list(
            Transaction.objects.filter(
                when__gte=from_date,
                when__lte=to_date,
                category__isnull=False
            ).values_list('pk', flat=True)
        )

        if len(pks) < MIN_CROSS_VALIDATION_TRANSACTIONS:
            return None

        if random_seed is None:
            random_seed = random.randint(0, 2**31)

        rng = random.Random(random_seed)
        rng.shuffle(pks)

        split_point = max(1, int(len(pks) * split_ratio))
        calibration_pks = pks[:split_point]
        validation_pks = pks[split_point:]

        return calibration_pks, validation_pks, random_seed

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
        to_date = datetime.combine(serializer.validated_data['to_date'], time.max, timezone.get_current_timezone())

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

    @decorators.action(detail=False, methods=["post"])
    def cross_validate(self, request):
        serializer = CrossValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            cls = CategoriserFactory.get_by_name(data['implementation'])
        except Exception:
            return response.Response(
                {'error': f"Unknown implementation: {data['implementation']}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from_date = datetime.combine(data['from_date'], time(), timezone.get_current_timezone())
        to_date = datetime.combine(data['to_date'], time.max, timezone.get_current_timezone())

        split_result = self._split_transaction_pks(
            from_date, to_date, data['split_ratio'],
            data.get('random_seed')
        )

        if split_result is None:
            total = Transaction.objects.filter(
                when__gte=from_date, when__lte=to_date, category__isnull=False
            ).count()
            error_data = {
                "status": "error",
                "message": (
                    f"Insufficient transactions for cross-validation. "
                    f"Found {total} categorised transactions in the period, "
                    f"minimum {MIN_CROSS_VALIDATION_TRANSACTIONS} required."
                ),
            }
            return response.Response(
                CrossValidationErrorSerializer(error_data).data
            )

        calibration_pks, validation_pks, seed = split_result

        # Train on calibration set
        categorisor = cls()
        calibration_qs = Transaction.objects.filter(pk__in=calibration_pks)
        categorisor.fit_queryset(calibration_qs)

        # Evaluate on validation set
        validation_qs = Transaction.objects.filter(pk__in=validation_pks).select_related('category')
        count = 0
        matched = 0
        failed = []
        category_stats = defaultdict(lambda: {"correct": 0, "total": 0})

        for trans in validation_qs:
            if trans.category:
                suggested = trans.suggest_category(categorisor)
                count += 1
                cat_name = trans.category.name
                category_stats[cat_name]["total"] += 1

                if suggested[0]['id'] == trans.category.id:
                    matched += 1
                    category_stats[cat_name]["correct"] += 1
                else:
                    failed.append({
                        "transaction": trans,
                        "modelled": suggested[0]
                    })

        category_metrics = [
            {
                "category_name": name,
                "correct": stats["correct"],
                "total": stats["total"],
                "precision": stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0,
            }
            for name, stats in sorted(category_stats.items())
        ]

        result = {
            "status": "ok",
            "random_seed": seed,
            "implementation": data['implementation'],
            "from_date": data['from_date'],
            "to_date": data['to_date'],
            "split_ratio": data['split_ratio'],
            "calibration_size": len(calibration_pks),
            "validation_size": len(validation_pks),
            "accuracy": matched / count if count > 0 else 0.0,
            "count": count,
            "matched": matched,
            "category_metrics": category_metrics,
            "failed": failed,
        }

        result_serializer = CrossValidationResponseSerializer(
            result, context={'request': request}
        )
        return response.Response(result_serializer.data)

    @decorators.action(detail=False, methods=["post"])
    def cross_validate_save(self, request):
        serializer = CrossValidateSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            CategoriserFactory.get_by_name(data['implementation'])
        except Exception:
            return response.Response(
                {'error': f"Unknown implementation: {data['implementation']}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from_date = datetime.combine(data['from_date'], time(), timezone.get_current_timezone())
        to_date = datetime.combine(data['to_date'], time.max, timezone.get_current_timezone())

        if data['recalibrate_full']:
            bin_data = self.calibrate(from_date, to_date, data['implementation'])
        else:
            missing = [f for f in ('split_ratio', 'random_seed') if f not in data]
            if missing:
                return response.Response(
                    {'error': f"{', '.join(missing)} required when recalibrate_full is false."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            split_result = self._split_transaction_pks(
                from_date, to_date, data['split_ratio'], data['random_seed']
            )
            if split_result is None:
                return response.Response(
                    {'error': 'Insufficient transactions in the period.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            calibration_pks = split_result[0]
            calibration_qs = Transaction.objects.filter(pk__in=calibration_pks)
            bin_data = self.calibrate(
                from_date, to_date, data['implementation'], queryset=calibration_qs
            )

        record = CategorisorModel.objects.create(
            name=data['name'],
            implementation=data['implementation'],
            from_date=data['from_date'],
            to_date=data['to_date'],
            model=bin_data
        )

        if data.get('set_as_default'):
            settings, _ = UserSettings.objects.get_or_create(user=request.user)
            settings.selected_categorisor = record
            settings.enable_db_categorisors = True
            settings.save()

        return response.Response(
            CategorisorSerializer(record, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @decorators.action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        categorisor = self.get_object()
        settings, _ = UserSettings.objects.get_or_create(user=request.user)
        settings.selected_categorisor = categorisor
        settings.enable_db_categorisors = True
        settings.save()

        return response.Response({
            "detail": "Model set as default.",
            "categorisor": CategorisorSerializer(categorisor, context={'request': request}).data,
        })
