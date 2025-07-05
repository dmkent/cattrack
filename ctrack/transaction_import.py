from enum import Enum
from typing import BinaryIO, Generator
from datetime import date

import pytz
import ofxparse
from quiffen import Qif


class Transaction:
    def __init__(self, when, description, amount):
        self.when = when
        self.description = description
        self.amount = amount

    def __repr__(self):
        return f"Transaction({self.when}, {self.description}, {self.amount})"


class TransactionFileFormat(Enum):
    OFX = 'ofx'
    QIF = 'qif'


class TransactionImporter:
    def __init__(self):
        pass

    def load_from_file(self, file_obj: str | BinaryIO, expected_format: TransactionFileFormat=None, from_date: date=None, to_date: date=None) -> list[Transaction]:
        # If this is a file-like object, use it directly.
        if hasattr(file_obj, 'read'):
            if expected_format is None:
                if hasattr(file_obj, 'name') and file_obj.name:
                    format_to_use = self.format_from_file_name(file_obj.name)
                else:
                    raise ValueError("Expected format must be specified for file-like objects.")
            else:
                format_to_use = expected_format
            file_to_use = file_obj
        else:
            # Attempt to open the file path.
            file_to_use = open(file_obj, 'rb')
            if expected_format is None:
                format_to_use = self.format_from_file_name(file_obj)
            else:
                format_to_use = expected_format   

        # Go process it.
        if format_to_use == TransactionFileFormat.OFX:
            return self.import_ofx(file_to_use, from_date=from_date, to_date=to_date)
        elif format_to_use == TransactionFileFormat.QIF:
            return list(self.import_qif(file_to_use))
        
        raise ValueError(f"Unsupported file format: {format_to_use}")

    def import_ofx(self, file_obj: BinaryIO, from_date: date = None, to_date: date = None) -> list[Transaction]:
        """Import transactions from an OFX file."""
        ofx = ofxparse.OfxParser.parse(file_obj)

        transactions: list[Transaction] = []
        for trans in ofx.account.statement.transactions:
            tdate = pytz.utc.localize(trans.date).date()
            if from_date and tdate < from_date:
                continue
            if to_date and tdate > to_date:
                continue

            transaction = Transaction(
                when=tdate,
                description=trans.memo,
                amount=trans.amount,
            )
            transactions.append(transaction)

        return transactions
    
    def import_qif(self, file_obj: BinaryIO) -> Generator[Transaction, None, None]:
        """Import transactions from a QIF file."""

        file_string = file_obj.read().decode('utf-8')
        separator = "\r\n" if file_string.count("\r\n") > 1 else "\n"
        qif = Qif.parse_string(file_string, separator=separator, day_first=True)

        first_account = list(qif.accounts.keys())[0]
        account = qif.accounts[first_account]

        tlist_key = list(account.transactions.keys())[0]
        tlist = account.transactions[tlist_key]
        
        for transaction in tlist:
            yield Transaction(
                when=transaction.date,
                description=transaction.payee,
                amount=transaction.amount
            )

    def format_from_file_name(self, file_name: str) -> TransactionFileFormat:
        """Determine the file format from the file name."""
        suffix = file_name.split('.')[-1].lower()
        if suffix == 'ofx':
            format_to_use = TransactionFileFormat.OFX
        elif suffix == 'qif':
            format_to_use = TransactionFileFormat.QIF
        else:
            raise ValueError("Expected format must be specified for file paths without a suffix.")
        return format_to_use