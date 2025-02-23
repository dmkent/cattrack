from datetime import datetime

from django.test import TestCase
import pytz

from ctrack import models


class AccountTestCase(TestCase):
    def setUp(self):
        models.Account.objects.create(name='test')

    def test_account(self):
        account = models.Account.objects.get(pk=1)
        self.assertEqual(account.name, 'test')

class TransactionTestCase(TestCase):
    def setUp(self):
        acc = models.Account.objects.create(name='test')
        trans = models.Transaction.objects.create(when=datetime(2013, 1, 1, tzinfo=pytz.utc), account=acc, amount=34.2)
        cat1 = models.Category.objects.create(name='Cash')
        cat2 = models.Category.objects.create(name='Groceries')

    def test_account(self):
        trans = models.Transaction.objects.get(pk=1)
        self.assertEqual(trans.when, datetime(2013, 1, 1, tzinfo=pytz.utc))
