"""Categorisation related implementations."""
import logging
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline
from django.conf import settings

from ctrack import models


logger = logging.getLogger(__name__)


class CategoriserFactory:
    @staticmethod
    def get_by_name(clsname):
        cls = globals()[clsname]

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
                logger.warn("Unable to load serialised categoriser.")
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

    def predict(self, text):
        """Suggest categories based on text."""
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

    def __init__(self, clf=None):
        self._clf = clf

    def fit_queryset(self, queryset):
        """Train a model using existing records."""
        data = queryset.values_list('description', 'category__name')
        self._fit_impl(data)

    def _fit_impl(self, data):
        data = np.array(data)

        text_clf = Pipeline([('vect', CountVectorizer()),
                             ('tfidf', TfidfTransformer()),
                             ('clf', SGDClassifier(loss='log', penalty='l2',
                                                   alpha=1e-3,
                                                   random_state=42)),
        ])

        text_clf = text_clf.fit(data[:, 0], data[:, 1])
        self._clf = text_clf

    def predict(self, text):
        """Use the model to predict categories."""
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
        probs = pd.Series(probs[0], index=self._clf.classes_).sort_values()[::-1]
        if probs.iloc[0] > self.THRESH:
            suggest = probs.iloc[:1]
        else:
            suggest = probs.loc[probs.cumsum() < self.THRESH]
        return suggest

    def to_bytes(self):
        """Serialise the model as a byte sequence."""
        return pickle.dumps(self._clf)

    @staticmethod
    def from_bytes(data):
        """Load object from bytes."""
        return SklearnCategoriser(pickle.loads(data))
