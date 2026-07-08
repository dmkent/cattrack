"""File-import orchestration.

Wraps ``transaction_import`` (OFX/Quicken) and ``pdf_item_reader`` (bill PDFs) so
that the parsing concerns stay out of ``models.py``. Models hold the data; these
functions turn an uploaded file into persisted rows.
"""

from ctrack.models import Bill, BillPdfScraperConfig, Transaction
from ctrack.transaction_import import TransactionImporter


def load_transactions(account, fobj, from_date=None, to_date=None, from_exist_latest=True):
    """Load transactions from an OFX/Quicken file into ``account``.

    Yields each persisted :class:`~ctrack.models.Transaction`. When
    ``from_exist_latest`` is set, importing resumes from the account's latest
    existing transaction date (ignoring any passed ``from_date``).
    """
    if from_exist_latest:
        try:
            latest_trans = account.transactions.latest('when')
            from_date = latest_trans.when.date()
        except Transaction.DoesNotExist:
            from_date = None

    loaded_transactions = TransactionImporter().load_from_file(
        fobj,
        from_date=from_date,
        to_date=to_date,
    )

    for trans in loaded_transactions:
        yield Transaction.objects.create(
            when=trans.when,
            account=account,
            description=trans.description,
            amount=trans.amount,
        )


def add_bill_from_file(series, fobj):
    """Add a new :class:`~ctrack.models.Bill` to ``series`` by scraping a PDF."""
    from ctrack.pdf_item_reader import extract_data

    data_from_file = extract_data(fobj, BillPdfScraperConfig.fetch_all_config())
    try:
        new_bill = Bill(
            description='test',
            due_amount=data_from_file['amount'],
            due_date=data_from_file['due_date'],
            series=series,
        )
    except KeyError as thrown:
        raise RuntimeError("Unable to get %s from PDF file." % thrown)
    new_bill.document = fobj
    new_bill.save()
    return new_bill
