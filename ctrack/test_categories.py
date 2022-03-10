from django.test import TestCase

from ctrack import categories


class SklCategoriserTests(TestCase):
    def setUp(self):
        self.categoriser = categories.SklearnCategoriser()
        self.categoriser._fit_impl([
            ["Shopping", "Shopping"],
            ["Transport first", "Transport"],
            ["Transport again", "Transport"],
            ["Groceries", "Shopping"],
            ["House", "House"],
            ["Training", "Training"],
            ["Transport/Car", "Car"],
            ["School", "School"],
            ["Childcare", "School"],
        ])

    def test_predict(self):
        predictions = self.categoriser.predict('Shopping')
        self.assertEqual(predictions.index[0], 'Shopping')

        predictions = self.categoriser.predict('Transport')
        self.assertEqual(predictions.index[0], 'Transport')

        predictions = self.categoriser.predict('X')
        self.assertEqual(predictions.index[0], 'School')
