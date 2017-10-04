from datetime import date, datetime, time, timedelta

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
        result = []
        for name, score in clf.predict(self.description).iteritems():
            cat = Category.objects.get(name=name)
            result.append({
                'name': cat.name,
                'id': cat.id,
                'score': int(round(score * 100.0, 0)),
            })
        return result


class SplitTransaction(Transaction):
    original_transaction = models.ForeignKey("Transaction",
                                             related_name="split_transactions")


class BalancePoint(models.Model):
    """An account balance at a point in time."""
    ref_date = models.DateField()
    balance = models.DecimalField(decimal_places=2, max_digits=8)
    account = models.ForeignKey("Account", related_name="balance_points")

    class Meta:
        get_latest_by = "ref_date"

    def __str__(self):
        return "{} == ${:.02f} on {}".format(
            self.account,
            self.balance,
            self.ref_date
        )

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
                    try:
                        trans.category = Category.objects.get(pk=cats[0].id)
                        trans.save()
                    except Category.DoesNotExist:
                        pass


    def daily_balance(self):
        """Get series of daily balance."""
        try:
            balance_point = self.balance_points.latest()
            init_balance = float(balance_point.balance)
            start = pytz.utc.localize(datetime.combine(balance_point.ref_date, time(0, 0)))
        except BalancePoint.DoesNotExist:
            init_balance = 0.0
            start = pytz.utc.localize(datetime(1990, 1, 1))
        transactions = (
            self.transaction_set
            .filter(when__gt=start, is_split=False)
            .order_by('when')
        )
        if len(transactions) <= 0:
            return pd.Series()
        series = pd.DataFrame({obj.id: {
            'when': obj.when,
            'amount': float(obj.amount)
        } for obj in transactions}).T
        series = series.groupby('when').sum()['amount']
        series = series.cumsum() + init_balance
        series = series.resample('D').ffill()
        return series

    @property
    def balance(self):
        """Get the latest balance for the account."""
        try:
            return self.daily_balance().iloc[-1]
        except IndexError:
            return None


class Category(models.Model):
    """A transaction category."""
    name = models.TextField(max_length=100)

    def __str__(self):
        return self.name


class PeriodDefinition(models.Model):
    """
        A flexible set of time periods for summarising transactions.

        Each object represents a series of periods, at the moment only the current
        and previous periods is used in the interface.

        A set of periods is defined using a pandas DateOffset string. i.e. something
        that can be passed to ``pd.to_offset``. For example, A, MS. See
        http://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
        for more.

        The ``anchor_date`` allows a period series to start on a particular date. This
        is useful for something like a fortnightly pay-period where we need to determine
        which of two potential days the series should start. The ``anchor_date`` must be
        at least 12 months in the past.
    """
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
            #end_date = date.today() + offset
            end_date = date(2016, 7, 18) + offset
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


class Bill(models.Model):
    """A single bill to be paid."""
    description = models.CharField(max_length=100)
    due_date = models.DateField()
    due_amount = models.DecimalField(max_digits=8, decimal_places=2)
    fixed_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    var_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    paying_transactions = models.ManyToManyField("Transaction",
                                                 related_name="pays_bill")
    document = models.FileField(null=True)
    series = models.ForeignKey('RecurringPayment', related_name="bills")

    @property
    def is_paid(self):
        return self.paying_transactions.aggregate(total=models.Sum('amount'))['total'] == -self.due_amount

    def __str__(self):
        return "{} bill of ${:.2f} due on {}".format(
            self.description,
            self.due_amount,
            self.due_date,
        )

    class Meta:
        ordering = ['-due_date',]


class RecurringPayment(models.Model):
    """A recurring bill series."""
    name = models.CharField(max_length=100)
    is_income = models.BooleanField(default=False)

    def bills_as_series(self):
        """Convert related Bill objects to time series."""
        arr = np.array(self.bills.values_list('due_date', 'due_amount'))
        return pd.Series(arr[:, 1], index=arr[:, 0])

    def next_due_date(self):
        """Calculate the due date of the next bill."""
        data = self.bills_as_series()
        days_between = [td.total_seconds() / 86400 for td in data.index.values[1:] - data.index.values[:-1]]
        mean_days = np.mean(days_between)
        last_due = data.index[-1]
        if mean_days < 10:
            freq = 'W'
            delta = timedelta(days=last_due.dayofweek)
        elif mean_days < 15:
            freq = '2W'
            delta = timedelta(days=last_due.dayofweek)
        elif mean_days < 33:
            freq = 'MS'
            delta = timedelta(days=last_due.day - 1)
        elif mean_days < 65:
            freq = '2MS'
            delta = timedelta(days=last_due.day - 1)
        elif mean_days < 100:
            freq = 'QS'
            delta = timedelta(days=last_due.day - 1)
        elif mean_days < 190:
            freq = '6MS'
            delta = timedelta(days=last_due.day - 1)
        elif mean_days < 367:
            freq = 'AS'
            delta = timedelta(days=last_due.dayofyear)
        else:
            freq = None
            delta = 0

        if freq is not None:
            offset = pd.datetools.to_offset(freq)
            return data.index[-1] + offset + delta
        return

    def __str__(self):
        if self.is_income:
            return "Income: {}".format(self.name)
        else:
            return "Bill: {}".format(self.name)
