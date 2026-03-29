"""ctrack REST API
"""
from rest_framework import serializers
from ctrack.api.transactions import TransactionSerializer
from ctrack.models import Category, CategorisorModel, Transaction

class CategorisorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CategorisorModel
        fields = ('url', 'id', 'name', 'implementation', 'from_date', 'to_date')

class DateRangeSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()

class CreateCategorisor(serializers.Serializer):
    name = serializers.CharField()
    implementation = serializers.CharField()
    from_date = serializers.DateTimeField()
    to_date = serializers.DateTimeField()

class SuggestionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    score = serializers.FloatField()

class FailedMatchSerializer(serializers.Serializer):
    transaction = TransactionSerializer()
    modelled = SuggestionSerializer(allow_null=True)
    
class ValidationResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    matched = serializers.IntegerField()
    failed = serializers.ListField(
        child=FailedMatchSerializer()
    )

class CrossValidateSerializer(serializers.Serializer):
    implementation = serializers.CharField(default='SklearnCategoriser')
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    split_ratio = serializers.FloatField(default=0.5, min_value=0.1, max_value=0.9)
    random_seed = serializers.IntegerField(required=False)

class CategoryMetricSerializer(serializers.Serializer):
    category_name = serializers.CharField()
    correct = serializers.IntegerField()
    total = serializers.IntegerField()
    precision = serializers.FloatField()

class CrossValidationErrorSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()

class CrossValidationResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    random_seed = serializers.IntegerField()
    implementation = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    split_ratio = serializers.FloatField()
    calibration_size = serializers.IntegerField()
    validation_size = serializers.IntegerField()
    accuracy = serializers.FloatField()
    count = serializers.IntegerField()
    matched = serializers.IntegerField()
    category_metrics = CategoryMetricSerializer(many=True)
    failed = FailedMatchSerializer(many=True)

class CrossValidateSaveSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=20)
    implementation = serializers.CharField(default='SklearnCategoriser')
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    recalibrate_full = serializers.BooleanField(default=True)
    split_ratio = serializers.FloatField(required=False, min_value=0.1, max_value=0.9)
    random_seed = serializers.IntegerField(required=False)
    set_as_default = serializers.BooleanField(default=False)


class CurrentCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_null=True)


class RecategorizeSuggestionSerializer(serializers.Serializer):
    transaction = TransactionSerializer()
    current_category = CurrentCategorySerializer()
    suggested_category = SuggestionSerializer()


class RecategorizeItemSerializer(serializers.Serializer):
    transaction = serializers.PrimaryKeyRelatedField(queryset=Transaction.objects.all())
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())


class ApplyRecategorizeSerializer(serializers.Serializer):
    updates = RecategorizeItemSerializer(many=True)

    def validate_updates(self, value):
        if len(value) == 0:
            raise serializers.ValidationError("At least one update is required.")
        if len(value) > 500:
            raise serializers.ValidationError("Maximum 500 updates per request.")

        transaction_pks = [item['transaction'].pk for item in value]
        if len(transaction_pks) != len(set(transaction_pks)):
            raise serializers.ValidationError("Duplicate transactions are not allowed.")

        return value
