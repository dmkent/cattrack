from dateutil.relativedelta import relativedelta
from django.db import models
import numpy as np
import pandas as pd
import pytz

from ctrack import categories

class Transaction(models.Model):
    """A single one-way transaction."""
    when = models.DateTimeField()
    account = models.ForeignKey("Account")
    amount = models.DecimalField(decimal_places=2, max_digits=8)
    is_split = models.BooleanField(default=False)
    category = models.ForeignKey("Category", null=True)
    description = models.CharField(max_length=500, null=True)

    def __str__(self):
        return "Transaction on {} of ${:.2f} at {}".format(
            self.account,
            self.amount,
            self.when,
        )

    def split(self, splits):
        if sum(splits.values()) != self.amount:
            raise ValueError("Split values do not sum to correct amount.")

        new_transactions = []
        for category, amount in splits.items():
            trans = SplitTransaction(original_transaction=self,
                                     category=category,
                                     amount=amount,
                                     when=self.when,
                                     description=self.description,
                                     account=self.account)
            new_transactions.append(trans)
        self.is_split = True
        self.save()
        [new_trans.save() for new_trans in new_transactions]

    def suggest_category(self):
        clf = categories.categoriser
        return [Category.objects.get(name=name) for name in clf.predict(self.description)]


class SplitTransaction(Transaction):
    original_transaction = models.ForeignKey("Transaction",
                                             related_name="split_transactions")


class Account(models.Model):
    """A logical account."""
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name

    def load_ofx(self, fname, from_date=None, to_date=None, from_exist_latest=True,
                 allow_categorisation=True):
        """Load an OFX file into the DB."""
        import ofxparse
        if hasattr(fname, 'read'):
            data = ofxparse.OfxParser.parse(fname)
        else:
            with open(fname, 'rb') as fobj:
                data = ofxparse.OfxParser.parse(fobj)

        if from_exist_latest:
            latest_trans = self.transaction_set.latest('when')
            from_date = latest_trans.when

        for trans in data.account.statement.transactions:
            tdate = pytz.utc.localize(trans.date)
            if from_date and tdate <= from_date:
                continue
            if to_date and tdate > to_date:
                continue

            trans = Transaction.objects.create(
                when=tdate,
                account=self,
                description=trans.memo,
                amount=trans.amount,
            )

            if allow_categorisation:
                cats = trans.suggest_category()
                if len(cats) == 1:
                    trans.category = cats[0]
                    trans.save()


class Category(models.Model):
    """A transaction category."""
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name


class PeriodDefinition(models.Model):
    label = models.CharField(max_length=20)
    anchor_date = models.DateField(null=True, blank=True)
    frequency = models.CharField(max_length=10)

    def __init__(self, *args, **kwargs):
        super(PeriodDefinition, self).__init__(*args, **kwargs)
        self._index = None
        self._ranges = None

    def __str__(self):
        return self.label

    @property
    def index(self):
        if self._index is None:
            offset = pd.datetools.to_offset(self.frequency)
            end_date = date.today() + offset
            start_date = end_date - relativedelta(years=1) - offset

            if self.anchor_date is None:
                dates = pd.date_range(start_date, end_date, 
                                      freq=self.frequency)
            else:
                if pd.Timestamp(self.anchor_date) > start_date:
                    raise ValueError("unable to anchor periods")
                    
                dates = pd.date_range(self.anchor_date, end_date, 
                                        freq=self.frequency)
                dates = dates[dates >= np.datetime64(start_date)]
            self._index = dates
        return self._index

    @property
    def date_ranges(self):
        if self._ranges is None:
            dates = self.index
            self._ranges = [(start, start_next - relativedelta(days=1)) 
                            for start, start_next in zip(dates[:-1], dates[1:])]
        return self._ranges

    @property
    def current(self):
        return self.date_ranges[-1]

    @property
    def previous(self):
        return self.date_ranges[-2]

    def summarise(self, queryset):
        for start, end in self.date_ranges:
            yield queryset.filter(
                when__gte=start, when__lte=end
            ).values('category', 'category__name').annotate(total=models.Sum('amount'))

    @property
    def option_specifiers(self):
        fmt = '%Y-%m-%d'
        return [
            {
                "label": "Current " + self.label,
                "from_date": self.current[0].strftime(fmt),
                "to_date": self.current[1].strftime(fmt),
                "id": self.pk,
                "offset": 1,
            }, {
                "label": "Previous " + self.label,
                "from_date": self.previous[0].strftime(fmt),
                "to_date": self.previous[1].strftime(fmt),
                "id": self.pk,
                "offset": 2,
            }
        ]