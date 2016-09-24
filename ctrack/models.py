from django.db import models
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
