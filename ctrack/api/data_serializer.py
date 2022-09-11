"""ctrack REST API
"""
import logging

from rest_framework import serializers

class LoadDataSerializer(serializers.Serializer):
    data_file = serializers.FileField()
