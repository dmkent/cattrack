#!/bin/env python
"""
Script to load CSV dump of data.

Run from django shell with "%run".

Expects the followin columns:
    1. date
    2. description
    3. category
    4. amount
    5. accountname
"""
import argparse

import pandas as pd

from ctrack.models import Transaction, Category, Account


def load_data(data_file):
    """Load data from ``data_file``"""
    data = pd.read_csv(data_file, index_col=0,
                       parse_dates=True, dayfirst=True)
    data.category = data.category.fillna('')

    for idx, row in data.iterrows():
        if row.category:
            cat = Category.objects.get_or_create(name=row.category)[0]
        else:
            cat = None
        acct = Account.objects.get_or_create(name=row.accountname)[0]
        Transaction.objects.create(when=idx,
                                   description=row.description,
                                   amount=row.amount,
                                   category=cat,
                                   account=acct)

def get_parser():
    """Get an ArgumentParser."""
    parser = argparse.ArgumentParser(description='Data loader.')
    parser.add_argument('data_file', type=argparse.FileType())

    return parser


def main(args=None):
    """Run the script."""
    if args is None:
        args = get_parser().parse_args()

    load_data(args.data_file)


if __name__ == '__main__':
    main()
