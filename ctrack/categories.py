"""Categorisation related implementations."""
import pickle

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline
from django.conf import settings

from ctrack import models


class Categoriser:
    """
        A base categoriser.

        Sub-classes need to provide ``fit`` and ``predict`` implentations.
    """
    def fit(self):
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
    def __init__(self, clf=None):
        self._clf = clf

    def fit(self):
        """Train a model using existing records."""
        data = models.Transaction.objects.filter(category__isnull=False).values_list('description', 'category__name')
        data = np.array(data)

        text_clf = Pipeline([('vect', CountVectorizer()),
                             ('tfidf', TfidfTransformer()),
                             ('clf', SGDClassifier(loss='log', penalty='l2',
                                                   alpha=1e-3, n_iter=5,
                                                   random_state=42)),
        ])

        text_clf = text_clf.fit(data[:, 0], data[:, 1])
        self._clf = text_clf

    def predict(self, text):
        """Use the model to predict categories."""
        if self._clf is None:
            self.fit()

        return self._clf.predict([text])

    def to_bytes(self):
        """Serialise the model as a byte sequence."""
        return pickle.dumps(self._clf)

    @staticmethod
    def from_bytes(data):
        """Load object from bytes."""
        return SklearnCategoriser(pickle.loads(data))

def _init():
    clsname = settings.CTRACK_CATEGORISER
    cls = globals()[clsname]
    return cls()
categoriser = _init()
