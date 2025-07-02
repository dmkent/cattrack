from enum import Enum
from typing import BinaryIO
from datetime import date

import pytz
import ofxparse


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
                raise ValueError("Expected format must be specified for file-like objects.")
            
            format_to_use = expected_format
            file_to_use = file_obj
        else:
            # Attempt to open the file path.
            file_to_use = open(file_obj, 'rb')
            if expected_format is None:
                suffix = file_obj.split('.')[-1].lower()
                if suffix == 'ofx':
                    format_to_use = 'ofx'
                else:
                    raise ValueError("Expected format must be specified for file paths without a suffix.") 
            else:
                format_to_use = expected_format   

        # Go process it.
        if format_to_use == TransactionFileFormat.OFX:
            return self.import_ofx(file_to_use, from_date=from_date, to_date=to_date)
        
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