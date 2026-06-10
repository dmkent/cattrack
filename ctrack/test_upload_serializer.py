"""Tests for file-upload validation on LoadDataSerializer."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from ctrack.api.serializers.common import LoadDataSerializer


class LoadDataSerializerTests(TestCase):
    def _upload(self, name, content=b"data"):
        return SimpleUploadedFile(name, content)

    def test_accepts_allowed_extension(self):
        serializer = LoadDataSerializer(data={"data_file": self._upload("statement.ofx")})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_accepts_pdf(self):
        serializer = LoadDataSerializer(data={"data_file": self._upload("bill.PDF")})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_unknown_extension(self):
        serializer = LoadDataSerializer(data={"data_file": self._upload("notes.txt")})
        self.assertFalse(serializer.is_valid())
        self.assertIn("data_file", serializer.errors)

    def test_rejects_oversized_file(self):
        big = b"x" * (LoadDataSerializer.MAX_UPLOAD_SIZE + 1)
        serializer = LoadDataSerializer(data={"data_file": self._upload("statement.ofx", big)})
        self.assertFalse(serializer.is_valid())
        self.assertIn("data_file", serializer.errors)
