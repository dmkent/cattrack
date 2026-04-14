"""Categorisation related implementations."""
from collections import Counter
import logging
import os
import pickle

import numpy as np
import pandas as pd
from django.db.models import Count
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline
from django.conf import settings

from ctrack import models


logger = logging.getLogger(__name__)


class CategoriserFactory:
    @staticmethod
    def get_by_name(clsname):
        try:
            cls = globals()[clsname]
        except KeyError as exc:
            raise ValueError("Unknown implementation: " + clsname) from exc

        if not issubclass(cls, Categoriser):
            raise Exception("Unable to find Categorisor: " + clsname)

        return cls

    @staticmethod
    def get_legacy_from_disk():
        try:
            dumped_file = settings.CTRACK_CATEGORISER_FILE
        except AttributeError:
            dumped_file = None
        try:
            clsname = settings.CTRACK_CATEGORISER
        except AttributeError:
            clsname = 'SklearnCategoriser'

        cls = globals()[clsname]

        if dumped_file and os.path.isfile(dumped_file):
            try:
                categoriser = cls.from_bytes(open(dumped_file, 'rb').read())
            except ModuleNotFoundError:
                logger.warning("Unable to load serialised categoriser.")
                categoriser = cls()
        else:
            categoriser = cls()
        return categoriser


class Categoriser:
    """
        A base categoriser.

        Sub-classes need to provide ``fit`` and ``predict`` implementations.
    """
    def fit(self):
        """Train a model using existing records."""
        self.fit_queryset(models.Transaction.objects.filter(category__isnull=False))

    def fit_queryset(self, queryset):
        raise NotImplementedError("Must be subclassed.")

    @classmethod
    def prepare_queryset(cls, queryset, **config):
        return {
            "queryset": queryset,
            "excluded_categories": [],
            "included_category_count": queryset.values('category').distinct().count(),
            "included_transaction_count": queryset.count(),
        }

    def predict(self, text):
        """Suggest categories based on text."""
        return self.predict_details(text)["suggestions"]

    def predict_details(self, text):
        """Return rich prediction details for evaluation and preview flows."""
        scores = self._predict_scores(text)
        suggestions = self._suggestions_from_scores(scores)
        if len(scores) == 0:
            return {
                "raw_predictions": scores,
                "suggestions": suggestions,
                "top_prediction": None,
                "top_probability": 0.0,
                "second_probability": 0.0,
                "margin": 0.0,
                "accepted": False,
                "gated_prediction": None,
            }

        top_prediction = scores.index[0]
        top_probability = float(scores.iloc[0])
        second_probability = float(scores.iloc[1]) if len(scores) > 1 else 0.0
        return {
            "raw_predictions": scores,
            "suggestions": suggestions,
            "top_prediction": top_prediction,
            "top_probability": top_probability,
            "second_probability": second_probability,
            "margin": top_probability - second_probability,
            "accepted": True,
            "gated_prediction": top_prediction,
        }

    def _predict_scores(self, text):
        raise NotImplementedError("Must be subclassed.")

    def _suggestions_from_scores(self, scores):
        raise NotImplementedError("Must be subclassed.")

    def to_bytes(self):
        """Serialise to bytes."""
        raise NotImplementedError("Must be subclassed.")

    @staticmethod
    def from_bytes(data):
        """Load object from bytes."""
        raise NotImplementedError("Must be subclassed.")


class SklearnCategoriser(Categoriser):
    """
        A Scikit Learn based categoriser.
    """
    #: The threshold at which to determine only a single category.
    #: If prob for a category is less than this then we give multiple
    #: suggestions.
    THRESH = 0.2

    DEFAULT_CONFIG = {
        'alpha': 1e-3,
    }

    def __init__(self, clf=None, **config):
        self.config = self.DEFAULT_CONFIG.copy()
        self.config.update({key: value for key, value in config.items() if value is not None})
        self.training_metadata = {}
        self._clf = clf

    def fit_queryset(self, queryset):
        """Train a model using existing records."""
        data = queryset.values_list('description', 'category__name')
        self._fit_impl(data)

    def _fit_impl(self, data):
        data = np.array(data)

        text_clf = Pipeline([('vect', CountVectorizer()),
                             ('tfidf', TfidfTransformer()),
                             ('clf', SGDClassifier(loss='log_loss', penalty='l2',
                                                   alpha=self.config['alpha'],
                                                   random_state=42)),
        ])

        text_clf = text_clf.fit(data[:, 0], data[:, 1])
        self._clf = text_clf

    def _predict_scores(self, text):
        """Use the model to predict category probabilities."""
        if self._clf is None:
            self.fit()
            try:
                dumped_file = settings.CTRACK_CATEGORISER_FILE
            except AttributeError:
                dumped_file = None
            if dumped_file:
                with open(dumped_file, 'wb') as fobj:
                    fobj.write(self.to_bytes())

        probs = self._clf.predict_proba([text])
        return pd.Series(probs[0], index=self._clf.classes_).sort_values()[::-1]

    def _suggestions_from_scores(self, scores):
        if len(scores) == 0:
            return scores
        if scores.iloc[0] > self.THRESH:
            return scores.iloc[:1]
        return scores.loc[scores.cumsum() < self.THRESH]

    def get_training_config(self):
        return dict(self.config)

    def get_training_metadata(self):
        return dict(self.training_metadata)

    def set_training_metadata(self, **metadata):
        self.training_metadata = dict(metadata)

    def to_bytes(self):
        """Serialise the model as a byte sequence."""
        return pickle.dumps({
            'clf': self._clf,
            'config': self.get_training_config(),
            'training_metadata': self.get_training_metadata(),
        })

    @staticmethod
    def from_bytes(data):
        """Load object from bytes."""
        loaded = pickle.loads(data)
        if isinstance(loaded, dict) and 'clf' in loaded:
            categoriser = SklearnCategoriser(
                clf=loaded['clf'],
                **loaded.get('config', {}),
            )
            categoriser.set_training_metadata(**loaded.get('training_metadata', {}))
            return categoriser

        return SklearnCategoriser(loaded)


class EnhancedSklearnCategoriser(Categoriser):
    """Enhanced categoriser with sparse-category exclusion and confidence gating."""

    DEFAULT_CONFIG = {
        'threshold': 0.6,
        'margin': 0.15,
        'min_df': 1,
        'max_df': 1.0,
        'alpha': 1e-3,
        'calibration_cv': 5,
        'min_category_samples': 3,
    }

    TOKEN_PATTERN = r'(?u)\b[a-zA-Z0-9][a-zA-Z0-9/\-]+\b'

    def __init__(self, clf=None, **config):
        self.config = self.DEFAULT_CONFIG.copy()
        self.config.update({key: value for key, value in config.items() if value is not None})
        self.training_metadata = {}
        self._clf = clf

    @classmethod
    def prepare_queryset(cls, queryset, **config):
        cfg = cls.DEFAULT_CONFIG.copy()
        cfg.update({key: value for key, value in config.items() if value is not None})
        min_category_samples = int(cfg['min_category_samples'])

        category_counts = list(
            queryset
            .values('category__name')
            .annotate(count=Count('pk'))
            .order_by('category__name')
        )

        included_names = [
            item['category__name']
            for item in category_counts
            if item['count'] >= min_category_samples
        ]
        excluded_categories = [
            {
                'category_name': item['category__name'],
                'count': item['count'],
            }
            for item in category_counts
            if item['count'] < min_category_samples
        ]

        included_queryset = queryset.filter(category__name__in=included_names)
        return {
            'queryset': included_queryset,
            'excluded_categories': excluded_categories,
            'included_category_count': len(included_names),
            'included_transaction_count': included_queryset.count(),
        }

    def fit_queryset(self, queryset):
        data = list(queryset.values_list('description', 'category__name'))
        self._fit_impl(data)

    def _normalise_document_frequency(self, value):
        if value is None:
            return value
        if isinstance(value, float) and value.is_integer() and value >= 1:
            return int(value)
        return value

    def _fit_impl(self, data):
        if not data:
            raise ValueError('Cannot train categoriser without any data.')

        data = np.array(data, dtype=object)
        category_counts = Counter(data[:, 1])
        min_class_count = min(category_counts.values())
        effective_cv = min(int(self.config['calibration_cv']), min_class_count)
        if effective_cv < 2:
            raise ValueError('Not enough samples per category for calibrated training.')

        alpha = float(self.config['alpha'])
        min_df = self._normalise_document_frequency(self.config['min_df'])
        max_df = self._normalise_document_frequency(self.config['max_df'])

        text_clf = Pipeline([
            ('vect', CountVectorizer(
                ngram_range=(1, 2),
                min_df=min_df,
                max_df=max_df,
                strip_accents='unicode',
                token_pattern=self.TOKEN_PATTERN,
            )),
            ('tfidf', TfidfTransformer()),
            ('clf', CalibratedClassifierCV(
                estimator=SGDClassifier(
                    loss='log_loss',
                    penalty='l2',
                    alpha=alpha,
                    random_state=42,
                ),
                cv=effective_cv,
                method='sigmoid',
            )),
        ])

        self._clf = text_clf.fit(data[:, 0], data[:, 1])

    def _predict_scores(self, text):
        probs = self._clf.predict_proba([text])
        return pd.Series(probs[0], index=self._clf.classes_).sort_values()[::-1]

    def _suggestions_from_scores(self, scores):
        if len(scores) == 0:
            return scores

        accepted = self._is_prediction_accepted(scores)
        if accepted:
            return scores.iloc[:1]
        return scores.iloc[:min(2, len(scores))]

    def _is_prediction_accepted(self, scores):
        if len(scores) == 0:
            return False

        top_probability = float(scores.iloc[0])
        second_probability = float(scores.iloc[1]) if len(scores) > 1 else 0.0
        return (
            top_probability >= float(self.config['threshold'])
            and (top_probability - second_probability) >= float(self.config['margin'])
        )

    def predict_details(self, text):
        scores = self._predict_scores(text)
        suggestions = self._suggestions_from_scores(scores)
        if len(scores) == 0:
            return {
                'raw_predictions': scores,
                'suggestions': suggestions,
                'top_prediction': None,
                'top_probability': 0.0,
                'second_probability': 0.0,
                'margin': 0.0,
                'accepted': False,
                'gated_prediction': None,
            }

        top_prediction = scores.index[0]
        top_probability = float(scores.iloc[0])
        second_probability = float(scores.iloc[1]) if len(scores) > 1 else 0.0
        accepted = self._is_prediction_accepted(scores)
        return {
            'raw_predictions': scores,
            'suggestions': suggestions,
            'top_prediction': top_prediction,
            'top_probability': top_probability,
            'second_probability': second_probability,
            'margin': top_probability - second_probability,
            'accepted': accepted,
            'gated_prediction': top_prediction if accepted else None,
        }

    def get_training_config(self):
        return dict(self.config)

    def get_training_metadata(self):
        return dict(self.training_metadata)

    def set_training_metadata(self, **metadata):
        self.training_metadata = dict(metadata)

    def to_bytes(self):
        return pickle.dumps({
            'clf': self._clf,
            'config': self.get_training_config(),
            'training_metadata': self.get_training_metadata(),
        })

    @staticmethod
    def from_bytes(data):
        loaded = pickle.loads(data)
        categoriser = EnhancedSklearnCategoriser(
            clf=loaded['clf'],
            **loaded.get('config', {}),
        )
        categoriser.set_training_metadata(**loaded.get('training_metadata', {}))
        return categoriser
