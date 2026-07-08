"""Pandas-heavy reporting computations.

Kept out of ``models.py`` so the models stay free of numpy/pandas number
crunching. The corresponding model methods are trivial delegators to these
functions.
"""

from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import pytz

from ctrack.models import BalancePoint


def account_daily_balance(account):
    """Return a daily-resampled balance series for ``account``."""
    try:
        balance_point = account.balance_points.latest()
        init_balance = float(balance_point.balance)
        start = pytz.utc.localize(datetime.combine(balance_point.ref_date, time(0, 0)))
    except BalancePoint.DoesNotExist:
        init_balance = 0.0
        start = pytz.utc.localize(datetime(1990, 1, 1))
    transactions = (
        account.transactions
        .filter(when__gt=start, is_split=False)
        .order_by('when')
    )
    if len(transactions) <= 0:
        return pd.Series(dtype='float64')
    series = pd.DataFrame({obj.id: {
        'when': obj.when,
        'amount': float(obj.amount)
    } for obj in transactions}).T
    series = series.groupby('when').sum()['amount']
    series = series.cumsum() + init_balance
    series = series.resample('D').ffill()
    return series


def account_balance(account):
    """Return the latest balance for ``account``, or ``None`` if unknown."""
    try:
        return account_daily_balance(account).iloc[-1]
    except IndexError:
        return None


def bills_as_series(payment):
    """Convert a recurring payment's related Bills to a time series."""
    arr = np.array(payment.bills.order_by('due_date').values_list('due_date', 'due_amount'))
    if len(arr) == 0:
        return pd.Series()
    return pd.Series(arr[:, 1], index=pd.DatetimeIndex(arr[:, 0])).astype(float)


def next_due_date(payment):
    """Estimate the due date of the next bill for ``payment``."""
    data = bills_as_series(payment)
    if len(data) == 0:
        return None
    days_between = data.index.to_series().diff().dt.days.values[1:]
    mean_days = np.mean(days_between)
    if not np.isfinite(mean_days):
        return None
    last_due = data.index[-1]
    return last_due + timedelta(days=mean_days)
