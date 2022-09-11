"""ctrack REST API
"""
from rest_framework import (serializers)

class SeriesSerializer(serializers.Serializer):
    label = serializers.DateTimeField(source='dtime')
    value = serializers.DecimalField(max_digits=20, decimal_places=2)