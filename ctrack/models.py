from datetime import date
import importlib

from dateutil.relativedelta import relativedelta
from django.db import models
from django.contrib.auth.models import User
import numpy as np
import pandas as pd


class Transaction(models.Model):
    """A single one-way transaction."""
    when = models.DateTimeField()
    account = models.ForeignKey("Account", on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(decimal_places=2, max_digits=8)
    is_split = models.BooleanField(default=False)
    category = models.ForeignKey("Category", on_delete=models.CASCADE, null=True)
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

    def suggest_category(self, clf, category_map=None):
        """Resolve ``clf``'s predictions to known categories.

        Trivial accessor -- see
        :func:`ctrack.services.categorisation_service.suggest_categories`.
        """
        from ctrack.services import categorisation_service
        return categorisation_service.suggest_categories(self, clf, category_map=category_map)

    class Meta:
        ordering = ["-when"]
        indexes = [models.Index(fields=["when"])]


class SplitTransaction(Transaction):
    original_transaction = models.ForeignKey("Transaction",
                                             on_delete=models.CASCADE,
                                             related_name="split_transactions")


class BalancePoint(models.Model):
    """An account balance at a point in time."""
    ref_date = models.DateField()
    balance = models.DecimalField(decimal_places=2, max_digits=8)
    account = models.ForeignKey("Account", on_delete=models.CASCADE, related_name="balance_points")

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
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def daily_balance(self):
        """Get series of daily balance."""
        from ctrack.services import reporting_service
        return reporting_service.account_daily_balance(self)

    @property
    def balance(self) -> float | None:
        """Get the latest balance for the account."""
        from ctrack.services import reporting_service
        return reporting_service.account_balance(self)


class Category(models.Model):
    """A transaction category."""
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    @property
    def group(self):
        return self.name.split(' - ')[0]

    @staticmethod
    def subcategory_prefix_from_name(name):
        if not name:
            return "None"
        prefix = name.split('-', 1)[0].strip()
        return prefix or "None"

    @property
    def subcategory_prefix(self):
        return Category.subcategory_prefix_from_name(self.name)
    
    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"


class CategoryGroup(models.Model):
    """A group of categories for aggregated transaction summaries."""
    name = models.CharField(max_length=100)
    categories = models.ManyToManyField(Category, related_name='category_groups')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "category groups"


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
            offset = pd.tseries.frequencies.to_offset(self.frequency)
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


class Bill(models.Model):
    """A single bill to be paid."""
    description = models.CharField(max_length=100)
    due_date = models.DateField()
    issued_date = models.DateField(null=True, blank=True)
    due_amount = models.DecimalField(max_digits=8, decimal_places=2)
    fixed_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    var_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    paying_transactions = models.ManyToManyField("Transaction",
                                                 related_name="pays_bill")
    document = models.FileField(null=True, upload_to='uploaded/bills')
    series = models.ForeignKey('RecurringPayment', on_delete=models.CASCADE, related_name="bills")

    @property
    def is_paid(self) -> bool:
        # Sum over the related manager rather than .aggregate() so that a
        # prefetched paying_transactions cache is reused (aggregate() always
        # hits the DB, defeating prefetch_related on list endpoints).
        payments = self.paying_transactions.all()
        if not payments:
            return False
        return sum(txn.amount for txn in payments) == -self.due_amount

    def __str__(self):
        return "{} bill of ${:.2f} due on {}".format(
            self.description,
            self.due_amount,
            self.due_date,
        )

    class Meta:
        ordering = ['-due_date',]
        indexes = [models.Index(fields=["due_date"])]


class RecurringPayment(models.Model):
    """A recurring bill series."""
    name = models.CharField(max_length=100)
    is_income = models.BooleanField(default=False)
    category = models.ForeignKey('Category', null=True, blank=True, on_delete=models.SET_NULL)

    def bills_as_series(self):
        """Convert related Bill objects to time series."""
        from ctrack.services import reporting_service
        return reporting_service.bills_as_series(self)

    def next_due_date(self) -> date | None:
        """Calculate the due date of the next bill."""
        from ctrack.services import reporting_service
        return reporting_service.next_due_date(self)

    def __str__(self):
        if self.is_income:
            return "Income: {}".format(self.name)
        else:
            return "Bill: {}".format(self.name)


class BillPdfScraperConfig(models.Model):
    """Represents configuration needed to scape data from bill PDF."""
    field = models.CharField(max_length=20)
    label_pattern = models.CharField(max_length=50)
    value_pattern = models.CharField(max_length=50)
    processor = models.CharField(max_length=200)

    @property
    def processor_func(self):
        """Map processor to function."""
        try:
            import builtins
            return getattr(builtins, self.processor)
        except AttributeError:
            pass
        try:
            package, name = self.processor.rsplit('.', 1)
            return getattr(importlib.import_module(package), name)
        except (ValueError, ImportError, AttributeError):
            pass

    @property
    def as_config(self):
        """Get configuration tuple for ``pdf_item_reader``."""
        return (self.field, self.label_pattern, self.value_pattern, self.processor_func)

    @classmethod
    def fetch_all_config(cls):
        """Get list of configuration objects."""
        return [instance.as_config for instance in cls.objects.all()]

    def __str__(self):
        return "{} using {}()".format(self.field, self.processor)


class BudgetEntryManager(models.Manager):
    use_for_related = True

    def for_period(self, effective_date, **kwargs):
        """Filter the budget entries for at given date."""
        return self.filter(valid_from__lte=effective_date, valid_to__gte=effective_date, **kwargs)

def current_year_start():
    return date(date.today().year, 1, 1)

def current_year_end():
    return date(date.today().year, 12, 31)

class BudgetEntry(models.Model):
    """Represents the budget for a category for a calendar month."""
    name = models.CharField(max_length=20, null=True)
    categories = models.ManyToManyField(Category)
    amount = models.DecimalField(decimal_places=2, max_digits=8)
    valid_from = models.DateField(default=current_year_start)
    valid_to = models.DateField(default=current_year_end)

    objects = BudgetEntryManager()


    def amount_over_period(self, from_date, to_date):
        """Scale the amount from monthly to whatever number of days."""
        period_days = (to_date - from_date).total_seconds() / 86400
        daily_amount = float(self.amount) * 12 / 365.25
        return daily_amount * period_days

    def pretty_valid(self):
        """Make a pretty string out of the valid period."""
        duration = (self.valid_to - self.valid_from).total_seconds() / 86400
        if duration >= 367:
            return "{} - {}".format(self.valid_from.year, self.valid_to.year)
        elif duration > 360:
            return "{}".format(self.valid_to.year)
        elif duration > 35:
            return self.valid_from.strftime("%b") + " - " + self.valid_to.strftime("%b %Y")
        elif duration > 27:
            return self.valid_to.strftime("%b %Y")
        else:
            return self.valid_from.strftime("%d %b") + " - " + self.valid_to.strftime("%d %b %Y")

    def name_from_categories(self):
        """Determine a name from the selected categories."""
        if self.categories.count() == 1:
            return self.categories.first().name

        names = self.categories.values_list("name", flat=True)
        name_parts = [name.split(' - ') for name in names]
        first_same = len(set([parts[0] == name_parts[0][0] for parts in name_parts])) == 1
        if first_same:
            return name_parts[0][0]

        return ", ".join(names)

    @property
    def pretty_name(self) -> str:
        if self.name:
            return self.name
        return self.name_from_categories()

    def __str__(self):
        return "{} : {} : {}".format(self.pretty_name, self.pretty_valid(), self.amount)

    class Meta:
        ordering = ["-valid_to"]
        verbose_name_plural = "budget entries"

class CategorisorModel(models.Model):
    name = models.CharField(max_length=20)
    implementation = models.CharField(max_length=200)
    from_date = models.DateField()
    to_date = models.DateField()
    model = models.BinaryField()
    training_config = models.JSONField(default=dict, blank=True)
    training_metrics = models.JSONField(default=dict, blank=True)
    exclusion_summary = models.JSONField(default=dict, blank=True)
    _model_clf = None

    def clf_model(self):
        if self._model_clf is None:
            from ctrack.services import categorisation_service
            self._model_clf = categorisation_service.load_categoriser(
                self.implementation, self.model
            )
        return self._model_clf

    def __str__(self):
        return "{} ({})".format(self.name, self.implementation)

    class Meta:
        verbose_name = "categorisor model"
        verbose_name_plural = "categorisor models"

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    selected_categorisor = models.ForeignKey(CategorisorModel, null=True, on_delete=models.SET_NULL)
    enable_db_categorisors = models.BooleanField(default=False)

    class Meta:
        verbose_name = "user settings"
        verbose_name_plural = "user settings"

    def get_clf_model(self):
        from ctrack.services import categorisation_service
        return categorisation_service.get_clf_model(self)

    def __str__(self) -> str:
        return "Settings for {}".format(self.user.get_short_name())