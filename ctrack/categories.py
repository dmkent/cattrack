from glob import glob

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline

from ctrack import models

def fit():
    data = models.Transaction.objects.filter(category__isnull=False).values_list('description', 'category__name')
    data = np.array(data)

    text_clf = Pipeline([('vect', CountVectorizer()),
                         ('tfidf', TfidfTransformer()),
                         ('clf', SGDClassifier(loss='log', penalty='l2',
                                               alpha=1e-3, n_iter=5,
                                               random_state=42)),
    ])

    text_clf = text_clf.fit(data[:, 0], data[:, 1])
    return text_clf

def predict(text_clf, description):
    return text_clf.predict([description])
