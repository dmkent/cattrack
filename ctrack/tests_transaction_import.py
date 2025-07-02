from decimal import Decimal
import io
from unittest import TestCase

from ctrack.transaction_import import TransactionImporter


class ImportTests(TestCase):
    def setUp(self):
        self.data = b"""
OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE
<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20250701070443
<LANGUAGE>ENG
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>AUD
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20230802000000
<TRNAMT>-0.51
<FITID>34234
<MEMO>Internal Transfer
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20230731000000
<TRNAMT>0.51
<FITID>54543
<MEMO>Interest Credit
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
        """
        self.data_obj = io.BytesIO(self.data)
        self.data_obj.seek(0)
        self.importer = TransactionImporter()

    def test_import_ofx(self):
        result = self.importer.import_ofx(self.data_obj)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].amount, Decimal('-0.51'))
        self.assertEqual(result[0].when.year, 2023)
        self.assertEqual(result[0].when.month, 8)
        self.assertEqual(result[0].when.day, 2)
        self.assertEqual(result[0].description, 'Internal Transfer')
        self.assertEqual(result[1].when.year, 2023)
        self.assertEqual(result[1].when.month, 7)
        self.assertEqual(result[1].when.day, 31)
        self.assertEqual(result[1].description, 'Interest Credit')
        self.assertEqual(result[1].amount, Decimal('0.51'))