"""ctrack REST API
"""
import logging
import re

from rest_framework import status, response, serializers, viewsets
from ctrack.categories import CategoriserFactory
from ctrack.models import CategorisorModel, Transaction


logger = logging.getLogger(__name__)


class CategorisorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CategorisorModel
        fields = ('url', 'id', 'name', 'implementation', 'from_date', 'to_date')


class CreateCategorisor(serializers.Serializer):
    name = serializers.CharField()
    implementation = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()


class CategorisorViewSet(viewsets.ModelViewSet):
    queryset = CategorisorModel.objects.all().order_by('name')
    serializer_class = CategorisorSerializer

    def create(self, request):
        serializer = CreateCategorisor(data=request.data)

        if serializer.is_valid():
            transactions = Transaction.objects.filter(
                when__gte=serializer.validated_data['from_date'],
                when__lte=serializer.validated_data['to_date'],
                category__isnull=False
            )

            try:
                cls = CategoriserFactory.get_by_name(serializer.validated_data['implementation'])
            except Exception:
                return response.Response({'error': 'Unknown implementation: '},
                    status=status.HTTP_400_BAD_REQUEST)

            categorisor = cls()
            categorisor.fit_queryset(transactions)

            bin_data = categorisor.to_bytes()

            record = CategorisorModel.objects.create(
                name=serializer.validated_data['name'],
                implementation=serializer.validated_data['implementation'],
                from_date=serializer.validated_data['from_date'],
                to_date=serializer.validated_data['to_date'],
                model=bin_data
            )

            return response.Response(CategorisorSerializer(record, context={'request': request}).data)
        else:
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

