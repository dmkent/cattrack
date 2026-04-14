"""ctrack REST API
"""
from collections import defaultdict
from datetime import datetime, time
import logging
import random

from django.utils import timezone
from rest_framework import decorators, status, response, viewsets
from ctrack.api.serializers.categorisor import (
    ApplyRecategorizeSerializer, CategorisorSerializer, CreateCategorisor,
    CrossValidateSerializer, CrossValidationErrorSerializer,
    CrossValidationResponseSerializer, CrossValidateSaveSerializer,
    DateRangeSerializer, RecategorizeSuggestionSerializer, ValidationResponseSerializer,
)
from ctrack.api.transactions import PageNumberSettablePagination
from ctrack.categories import CategoriserFactory
from ctrack.models import Category, CategorisorModel, Transaction, UserSettings


logger = logging.getLogger(__name__)

MIN_CROSS_VALIDATION_TRANSACTIONS = 20


class CategorisorViewSet(viewsets.ModelViewSet):
    queryset = CategorisorModel.objects.all().order_by('name')
    serializer_class = CategorisorSerializer

    CATEGORISER_OPTION_KEYS = (
        'threshold', 'margin', 'min_df', 'max_df', 'alpha',
        'calibration_cv', 'min_category_samples',
    )

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

    def calibrate(self, from_date, to_date, implementation, queryset=None, options=None, return_categoriser=False):
        if queryset is None:
            queryset = Transaction.objects.filter(
                when__gte=from_date,
                when__lte=to_date,
                category__isnull=False
            )

        cls = CategoriserFactory.get_by_name(implementation)

        categorisor = cls(**(options or {}))
        categorisor.fit_queryset(queryset)

        if return_categoriser:
            return categorisor

        return categorisor.to_bytes()

    def _extract_categoriser_options(self, data):
        return {
            key: data[key]
            for key in self.CATEGORISER_OPTION_KEYS
            if key in data and data[key] is not None
        }

    def _build_training_config(self, data, options):
        config = {
            'implementation': data['implementation'],
            'from_date': data['from_date'].isoformat(),
            'to_date': data['to_date'].isoformat(),
            **options,
        }
        for key in ('split_ratio', 'random_seed', 'recalibrate_full'):
            if key in data:
                value = data.get(key)
                if value is not None:
                    config[key] = value
        return config

    def _prepare_training_queryset(self, queryset, cls, options):
        prepared = cls.prepare_queryset(queryset, **options)
        return {
            'queryset': prepared['queryset'],
            'excluded_categories': prepared.get('excluded_categories', []),
            'included_category_count': prepared.get('included_category_count', 0),
            'included_transaction_count': prepared.get('included_transaction_count', 0),
        }

    def _build_exclusion_summary(self, prepared):
        return {
            'excluded_categories': prepared['excluded_categories'],
            'included_category_count': prepared['included_category_count'],
            'included_transaction_count': prepared['included_transaction_count'],
        }

    def _build_modelled_suggestion(self, category_map, name, score):
        category_id = category_map.get(name)
        if category_id is None:
            return None
        return {
            'name': name,
            'id': category_id,
            'score': int(round(score * 100.0, 0)),
        }

    def _build_comparison(self, candidate_metrics, baseline_metrics):
        metric_keys = ('accuracy', 'overall_accuracy', 'auto_precision', 'coverage', 'review_count')
        return {
            'baseline': {
                'implementation': 'SklearnCategoriser',
                **{key: baseline_metrics[key] for key in metric_keys},
            },
            'delta': {
                key: candidate_metrics[key] - baseline_metrics[key]
                for key in ('accuracy', 'overall_accuracy', 'auto_precision', 'coverage')
            },
        }

    def _summarise_training_metrics(self, evaluation):
        return {
            'accuracy': evaluation['accuracy'],
            'overall_accuracy': evaluation['overall_accuracy'],
            'count': evaluation['count'],
            'matched': evaluation['matched'],
            'auto_matched': evaluation['auto_matched'],
            'auto_precision': evaluation['auto_precision'],
            'coverage': evaluation['coverage'],
            'review_count': evaluation['review_count'],
            'category_metrics': evaluation['category_metrics'],
        }

    def _split_queryset_pks(self, queryset, split_ratio, random_seed=None):
        """Split a queryset into calibration and validation sets by primary key."""
        pks = list(queryset.values_list('pk', flat=True))

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

    def _evaluate_validation_queryset(self, categorisor, validation_qs, category_map):
        count = 0
        matched = 0
        auto_matched = 0
        review_count = 0
        failed = []
        category_stats = defaultdict(lambda: {
            'correct': 0,
            'total': 0,
            'auto_correct': 0,
            'auto_total': 0,
        })

        for trans in validation_qs.select_related('category'):
            if not trans.category:
                continue

            details = categorisor.predict_details(trans.description or '')
            count += 1
            actual_name = trans.category.name
            stats = category_stats[actual_name]
            stats['total'] += 1

            top_prediction = details['top_prediction']
            if top_prediction and category_map.get(top_prediction) == trans.category.id:
                matched += 1
                stats['correct'] += 1

            if details['accepted'] and details['gated_prediction']:
                stats['auto_total'] += 1
                if category_map.get(details['gated_prediction']) == trans.category.id:
                    auto_matched += 1
                    stats['auto_correct'] += 1
                else:
                    failed.append({
                        'transaction': trans,
                        'modelled': self._build_modelled_suggestion(
                            category_map,
                            details['gated_prediction'],
                            details['top_probability'],
                        ),
                    })
            else:
                review_count += 1

        category_metrics = [
            {
                'category_name': name,
                'correct': stats['correct'],
                'total': stats['total'],
                'precision': stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0,
                'auto_correct': stats['auto_correct'],
                'auto_total': stats['auto_total'],
                'auto_precision': (
                    stats['auto_correct'] / stats['auto_total']
                    if stats['auto_total'] > 0 else 0.0
                ),
                'coverage': stats['auto_total'] / stats['total'] if stats['total'] > 0 else 0.0,
            }
            for name, stats in sorted(category_stats.items())
        ]

        accuracy = matched / count if count > 0 else 0.0
        coverage = (count - review_count) / count if count > 0 else 0.0
        auto_precision = auto_matched / (count - review_count) if count > review_count else 0.0

        return {
            'accuracy': accuracy,
            'overall_accuracy': accuracy,
            'count': count,
            'matched': matched,
            'auto_matched': auto_matched,
            'auto_precision': auto_precision,
            'coverage': coverage,
            'review_count': review_count,
            'category_metrics': category_metrics,
            'failed': failed,
        }

    @decorators.action(detail=True, methods=["get", "post"])
    def recalibrate(self, request, pk=None):
        details = self.get_object()
        options = {
            key: details.training_config.get(key)
            for key in self.CATEGORISER_OPTION_KEYS
            if details.training_config.get(key) is not None
        }
        cls = CategoriserFactory.get_by_name(details.implementation)
        queryset = Transaction.objects.filter(
            when__gte=details.from_date,
            when__lte=details.to_date,
            category__isnull=False,
        )
        prepared = self._prepare_training_queryset(queryset, cls, options)
        categorisor = cls(**options)
        categorisor.set_training_metadata(**self._build_exclusion_summary(prepared))
        categorisor.fit_queryset(prepared['queryset'])
        bin_data = categorisor.to_bytes()
        details.model = bin_data
        details.exclusion_summary = self._build_exclusion_summary(prepared)
        details.save()

        return response.Response("ok")

    def _get_date_range_and_clf(self, request, **extra_filters):
        """Parse date range from query params, query transactions, and load classifier."""
        categorisor = self.get_object()
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        from_date = datetime.combine(serializer.validated_data['from_date'], time(), timezone.get_current_timezone())
        to_date = datetime.combine(serializer.validated_data['to_date'], time.max, timezone.get_current_timezone())

        transactions = Transaction.objects.select_related('category').filter(
            when__gte=from_date, when__lte=to_date, **extra_filters,
        )
        clf = categorisor.clf_model()
        return transactions, clf

    @decorators.action(detail=True, methods=["get"], serializer_class=DateRangeSerializer)
    def validate(self, request, pk=None):
        transactions, clf = self._get_date_range_and_clf(request)

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
        options = self._extract_categoriser_options(data)

        try:
            cls = CategoriserFactory.get_by_name(data['implementation'])
        except Exception:
            return response.Response(
                {'error': f"Unknown implementation: {data['implementation']}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from_date = datetime.combine(data['from_date'], time(), timezone.get_current_timezone())
        to_date = datetime.combine(data['to_date'], time.max, timezone.get_current_timezone())

        base_queryset = Transaction.objects.filter(
            when__gte=from_date,
            when__lte=to_date,
            category__isnull=False,
        )
        prepared = self._prepare_training_queryset(base_queryset, cls, options)
        split_result = self._split_queryset_pks(
            prepared['queryset'],
            data['split_ratio'],
            data.get('random_seed')
        )

        if split_result is None:
            total = prepared['included_transaction_count']
            error_data = {
                "status": "error",
                "message": (
                    f"Insufficient transactions for cross-validation. "
                    f"Found {total} categorised transactions in the period after exclusions, "
                    f"minimum {MIN_CROSS_VALIDATION_TRANSACTIONS} required."
                ),
            }
            return response.Response(
                CrossValidationErrorSerializer(error_data).data
            )

        calibration_pks, validation_pks, seed = split_result

        categorisor = cls(**options)
        categorisor.set_training_metadata(**self._build_exclusion_summary(prepared))
        calibration_qs = prepared['queryset'].filter(pk__in=calibration_pks)
        categorisor.fit_queryset(calibration_qs)

        category_map = {c.name: c.id for c in Category.objects.all()}

        validation_qs = prepared['queryset'].filter(pk__in=validation_pks)
        evaluation = self._evaluate_validation_queryset(categorisor, validation_qs, category_map)

        result = {
            "status": "ok",
            "random_seed": seed,
            "implementation": data['implementation'],
            "from_date": data['from_date'],
            "to_date": data['to_date'],
            "split_ratio": data['split_ratio'],
            "calibration_size": len(calibration_pks),
            "validation_size": len(validation_pks),
            **evaluation,
            **self._build_exclusion_summary(prepared),
        }

        if data.get('compare_against_baseline') and data['implementation'] != 'SklearnCategoriser':
            baseline_cls = CategoriserFactory.get_by_name('SklearnCategoriser')
            baseline = baseline_cls()
            baseline.fit_queryset(calibration_qs)
            baseline_evaluation = self._evaluate_validation_queryset(baseline, validation_qs, category_map)
            result['comparison'] = self._build_comparison(result, baseline_evaluation)

        result_serializer = CrossValidationResponseSerializer(
            result, context={'request': request}
        )
        return response.Response(result_serializer.data)

    @decorators.action(detail=False, methods=["post"])
    def cross_validate_save(self, request):
        serializer = CrossValidateSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        options = self._extract_categoriser_options(data)

        try:
            cls = CategoriserFactory.get_by_name(data['implementation'])
        except Exception:
            return response.Response(
                {'error': f"Unknown implementation: {data['implementation']}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from_date = datetime.combine(data['from_date'], time(), timezone.get_current_timezone())
        to_date = datetime.combine(data['to_date'], time.max, timezone.get_current_timezone())

        base_queryset = Transaction.objects.filter(
            when__gte=from_date,
            when__lte=to_date,
            category__isnull=False,
        )
        prepared = self._prepare_training_queryset(base_queryset, cls, options)
        exclusion_summary = self._build_exclusion_summary(prepared)
        training_config = self._build_training_config(data, options)

        if prepared['included_transaction_count'] == 0:
            return response.Response(
                {'error': 'No categorised transactions found in the specified period after exclusions.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        training_metrics = {
            'trained_on_full_dataset': data['recalibrate_full'],
            'included_transaction_count': prepared['included_transaction_count'],
            'included_category_count': prepared['included_category_count'],
        }

        if data['recalibrate_full']:
            categorisor = cls(**options)
            categorisor.set_training_metadata(**exclusion_summary)
            categorisor.fit_queryset(prepared['queryset'])
            bin_data = categorisor.to_bytes()
        else:
            missing = [f for f in ('split_ratio', 'random_seed') if f not in data]
            if missing:
                return response.Response(
                    {'error': f"{', '.join(missing)} required when recalibrate_full is false."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            split_result = self._split_queryset_pks(
                prepared['queryset'], data['split_ratio'], data['random_seed']
            )
            if split_result is None:
                return response.Response(
                    {'error': 'Insufficient transactions in the period after exclusions.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            calibration_pks, validation_pks, seed = split_result
            training_config['random_seed'] = seed
            calibration_qs = prepared['queryset'].filter(pk__in=calibration_pks)
            categorisor = cls(**options)
            categorisor.set_training_metadata(**exclusion_summary)
            categorisor.fit_queryset(calibration_qs)
            bin_data = categorisor.to_bytes()

            category_map = {c.name: c.id for c in Category.objects.all()}
            evaluation = self._evaluate_validation_queryset(
                categorisor,
                prepared['queryset'].filter(pk__in=validation_pks),
                category_map,
            )
            training_metrics.update({
                'split_ratio': data['split_ratio'],
                'random_seed': seed,
                **self._summarise_training_metrics(evaluation),
            })

        record = CategorisorModel.objects.create(
            name=data['name'],
            implementation=data['implementation'],
            from_date=data['from_date'],
            to_date=data['to_date'],
            model=bin_data,
            training_config=training_config,
            training_metrics=training_metrics,
            exclusion_summary=exclusion_summary,
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

    @decorators.action(detail=True, methods=["get"], serializer_class=DateRangeSerializer)
    def preview_recategorize(self, request, pk=None):
        transactions, clf = self._get_date_range_and_clf(request, is_split=False)
        category_map = {c.name: c for c in Category.objects.all()}
        changes = []

        for trans in transactions:
            if not trans.description:
                continue
            details = clf.predict_details(trans.description)
            if not details['accepted']:
                continue

            predictions = details['suggestions']
            suggested = [
                {'name': name, 'id': category_map[name].id,
                 'score': int(round(score * 100.0, 0))}
                for name, score in predictions.items()
                if name in category_map
            ]
            if not suggested:
                continue
            top = suggested[0]
            if top['id'] != trans.category_id:
                changes.append({
                    "transaction": trans,
                    "current_category": {
                        "id": trans.category_id,
                        "name": trans.category.name if trans.category else None,
                    },
                    "suggested_category": top,
                })

        paginator = PageNumberSettablePagination()
        page = paginator.paginate_queryset(changes, request)
        result = RecategorizeSuggestionSerializer(
            page, many=True, context={'request': request}
        )
        return paginator.get_paginated_response(result.data)

    @decorators.action(detail=True, methods=["post"], serializer_class=ApplyRecategorizeSerializer)
    def apply_recategorize(self, request, pk=None):
        self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updates = serializer.validated_data['updates']
        transactions = []
        for item in updates:
            item['transaction'].category = item['category']
            transactions.append(item['transaction'])
        Transaction.objects.bulk_update(transactions, ['category'])

        return response.Response({"updated_count": len(updates)})
