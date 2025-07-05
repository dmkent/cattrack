from decimal import Decimal
import io
import tempfile
from unittest import TestCase

from ctrack.transaction_import import TransactionFileFormat, TransactionImporter


class ImportTests(TestCase):
    def setUp(self):
        self.ofx_data = b"""
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
        self.ofx_data_obj = io.BytesIO(self.ofx_data)
        self.ofx_data_obj.seek(0)

        self.qif_data = b"""
!Type:Bank
D20/06/2025
T-160.00
N1
PIB TRANSFER 756745 TO 346645745 5:05PM
LDEBIT
^
D01/06/2025
T-690.00
N2
PTo Phone 05:05PM 26Jun
LDEBIT
^
        """
        self.qif_data_obj = io.BytesIO(self.qif_data)
        self.qif_data_obj.seek(0)
        self.qif_data_obj_line_return = io.BytesIO(self.qif_data.replace(b'\n', b'\r\n'))
        self.qif_data_obj_line_return.seek(0)

        self.importer = TransactionImporter()

    def test_import_ofx(self):
        result = self.importer.import_ofx(self.ofx_data_obj)
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

    def test_import_qif(self):
        result = list(self.importer.import_qif(self.qif_data_obj))
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].amount, Decimal('-160.00'))
        self.assertEqual(result[0].when.year, 2025)
        self.assertEqual(result[0].when.month, 6)
        self.assertEqual(result[0].when.day, 20)
        self.assertEqual(result[0].description, 'IB TRANSFER 756745 TO 346645745 5:05PM')
        self.assertEqual(result[1].amount, Decimal('-690.00'))
        self.assertEqual(result[1].when.year, 2025)
        self.assertEqual(result[1].when.month, 6)
        self.assertEqual(result[1].when.day, 1)
        self.assertEqual(result[1].description, 'To Phone 05:05PM 26Jun')

    def test_load_from_file_ofx(self):
        result = self.importer.load_from_file(self.ofx_data_obj, expected_format=TransactionFileFormat.OFX)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].amount, Decimal('-0.51'))
        self.assertEqual(result[1].amount, Decimal('0.51'))

    def test_load_from_file_qif(self):
        result = self.importer.load_from_file(self.qif_data_obj, expected_format=TransactionFileFormat.QIF)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].amount, Decimal('-160.00'))
        self.assertEqual(result[1].amount, Decimal('-690.00'))

    def test_load_from_file_qif_line_return(self):
        result = self.importer.load_from_file(self.qif_data_obj_line_return, expected_format=TransactionFileFormat.QIF)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].amount, Decimal('-160.00'))
        self.assertEqual(result[1].amount, Decimal('-690.00'))

    def test_load_from_file_no_format(self):
        with self.assertRaises(ValueError):
            self.importer.load_from_file(self.ofx_data_obj)

    def test_load_from_file_invalid_format(self):
        with self.assertRaises(ValueError):
            self.importer.load_from_file(self.ofx_data_obj, expected_format='invalid_format')

    def test_load_from_file_path(self):
        # Create a temporary file to simulate a file path
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(self.ofx_data)
            temp_file.seek(0)
            result = self.importer.load_from_file(temp_file.name, expected_format=TransactionFileFormat.OFX)
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].amount, Decimal('-0.51'))
            self.assertEqual(result[1].amount, Decimal('0.51'))

    def test_load_from_file_path_no_format(self):
        # Create a temporary file to simulate a file path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ofx") as temp_file:
            temp_file.write(self.ofx_data)
            temp_file.seek(0)
            result = self.importer.load_from_file(temp_file.name)
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].amount, Decimal('-0.51'))
            self.assertEqual(result[1].amount, Decimal('0.51'))

    def test_load_from_file_path_no_format_qif(self):
        # Create a temporary file to simulate a file path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".qif") as temp_file:
            temp_file.write(self.qif_data)
            temp_file.seek(0)
            result = self.importer.load_from_file(temp_file.name)
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].amount, Decimal('-160.00'))
            self.assertEqual(result[1].amount, Decimal('-690.00'))