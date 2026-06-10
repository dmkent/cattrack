"""Categorisation helpers.

Wraps ``ctrack.categories`` (the sklearn classifier machinery) so that
``models.py`` no longer imports it directly. Models keep trivial accessors that
delegate here.
"""

from ctrack.categories import CategoriserFactory


def load_categoriser(implementation, model_bytes):
    """Rebuild a classifier instance from its stored bytes."""
    cls = CategoriserFactory.get_by_name(implementation)
    return cls.from_bytes(model_bytes)


def get_clf_model(user_settings):
    """Resolve the classifier a user's settings select.

    Falls back to the legacy on-disk model unless DB-stored categorisors are
    enabled, in which case the user's ``selected_categorisor`` is loaded.
    """
    if not user_settings.enable_db_categorisors:
        return CategoriserFactory.get_legacy_from_disk()
    return user_settings.selected_categorisor.clf_model()


def suggest_categories(transaction, clf, category_map=None):
    """Resolve a classifier's predictions for ``transaction`` to known categories.

    Returns a list of ``{name, id, score}`` dicts in the order produced by
    ``clf.predict`` (the classifier's own ranking; this does not re-sort). Labels
    with no matching :class:`~ctrack.models.Category` are skipped, so the result
    may be empty -- callers must not assume ``[0]`` exists.

    ``category_map`` is an optional ``{name: id}`` mapping. When evaluating many
    transactions, build it once and pass it in to avoid a per-prediction
    ``Category`` lookup (the previous N+1). When omitted it is built once here.
    """
    if category_map is None:
        from ctrack.models import Category
        category_map = dict(Category.objects.values_list('name', 'id'))
    result = []
    for name, score in clf.predict(transaction.description).items():
        category_id = category_map.get(name)
        if category_id is None:
            continue
        result.append({
            'name': name,
            'id': category_id,
            'score': int(round(score * 100.0, 0)),
        })
    return result
