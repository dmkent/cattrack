"""ctrack REST API
"""
from rest_framework import serializers

class LoadDataSerializer(serializers.Serializer):
    data_file = serializers.FileField()
    from_date = serializers.DateField(required=False, help_text="Start date for the data load")
    to_date = serializers.DateField(required=False, help_text="End date for the data load")
