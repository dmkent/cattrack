"""ctrack REST API - UserSettings serializer"""

from rest_framework import serializers
from ctrack.models import UserSettings, CategorisorModel


class UserSettingsSerializer(serializers.ModelSerializer):
    selected_categorisor = serializers.PrimaryKeyRelatedField(
        queryset=CategorisorModel.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = UserSettings
        fields = ("id", "selected_categorisor")

    def validate(self, attrs):
        """Ensure enable_db_categorisors is disabled when selected_categorisor is cleared.

        If selected_categorisor is set to None while enable_db_categorisors is True,
        automatically disable enable_db_categorisors to prevent get_clf_model() from
        crashing when accessing self.selected_categorisor.clf_model().
        """
        selected = attrs.get(
            "selected_categorisor",
            self.instance.selected_categorisor if self.instance else None,
        )
        if selected is None and getattr(self.instance, "enable_db_categorisors", False):
            attrs["enable_db_categorisors"] = False
        return attrs
