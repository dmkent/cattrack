from datetime import datetime
from django.template import loader
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import pytz

from ctrack.models import Category, CategorisorModel, Transaction

@login_required
def validate_categorisor(request, cid, from_date_str, to_date_str):
    categorisor = CategorisorModel.objects.get(id=cid)
    clf = categorisor.clf_model()

    from_date = pytz.utc.localize(datetime.strptime(from_date_str, '%Y-%m-%d'))
    to_date = pytz.utc.localize(datetime.strptime(to_date_str, '%Y-%m-%d'))
    transactions = Transaction.objects.filter(when__gte=from_date, when__lte=to_date)

    category_map = dict(Category.objects.values_list('name', 'id'))
    validation = []
    for transaction in transactions:
        suggested = transaction.suggest_category(clf, category_map=category_map)
        if suggested:
            validation.append({
                'transaction': transaction,
                'category': suggested[0],
            })

    template = loader.get_template('ctrack/validation.html')
    context = {
        'validations': validation
    }
    return HttpResponse(template.render(context, request))