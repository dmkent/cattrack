"""ctrack REST API - UserSettings serializer
"""
from rest_framework import serializers
from ctrack.models import UserSettings, CategorisorModel


class UserSettingsSerializer(serializers.HyperlinkedModelSerializer):
    selected_categorisor = serializers.PrimaryKeyRelatedField(
        queryset=CategorisorModel.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = UserSettings
        fields = ('url', 'id', 'selected_categorisor')
