"""Shared serializers used across multiple API modules."""
import os

from rest_framework import serializers


class SeriesSerializer(serializers.Serializer):
    """A single (label, value) point in a time series."""
    label = serializers.DateTimeField(source='dtime')
    value = serializers.DecimalField(max_digits=20, decimal_places=2)


class LoadDataSerializer(serializers.Serializer):
    """Upload payload for importing transactions / bills from a file."""

    # 25 MB ceiling — generous for statement exports, guards against abuse.
    MAX_UPLOAD_SIZE = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS = ('.ofx', '.qfx', '.qif', '.pdf')

    data_file = serializers.FileField()
    from_date = serializers.DateField(required=False, help_text="Start date for the data load")
    to_date = serializers.DateField(required=False, help_text="End date for the data load")

    def validate_data_file(self, value):
        if value.size > self.MAX_UPLOAD_SIZE:
            max_mb = self.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise serializers.ValidationError(
                f"File too large (max {max_mb} MB)."
            )
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(self.ALLOWED_EXTENSIONS)
            raise serializers.ValidationError(
                f"Unsupported file type '{ext or value.name}'. Allowed: {allowed}."
            )
        return value
