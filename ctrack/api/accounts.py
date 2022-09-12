"""ctrack REST API
"""
import logging

from rest_framework import (decorators, response,
                            serializers, status, viewsets)
from ctrack.api.data_serializer import LoadDataSerializer
from ctrack.api.series_serializer import SeriesSerializer
from ctrack.models import (Account, Category)


logger = logging.getLogger(__name__)


# Serializers define the API representation.
class AccountSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Account
        fields = ('url', 'id', 'name', 'balance')


# ViewSets define the view behavior.
class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    @decorators.action(detail=True, methods=["post"])
    def load(self, request, pk=None):
        account = self.get_object()
        serializer = LoadDataSerializer(data=request.data)
        if serializer.is_valid():
            try:
                transactions = account.load_ofx(serializer.validated_data['data_file'])
            except (ValueError, IOError, TypeError):
                logger.exception("OFX parse error")
                return response.Response("Unable to load file. Bad format?",
                                         status=status.HTTP_400_BAD_REQUEST)

            clf = request.user.usersettings.get_clf_model()
            for trans in transactions:
                cats = trans.suggest_category(clf)
                if len(cats) == 1:
                    try:
                        trans.category = Category.objects.get(pk=cats[0]['id'])
                        trans.save()
                    except Category.DoesNotExist:
                        pass
            return response.Response({'status': 'loaded'})
        else:
            return response.Response(serializer.errors,
                                     status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=["get"])
    def series(self, request, pk=None):
        series = self.get_object().daily_balance()
        series.index.name = 'dtime'
        serialised = SeriesSerializer(series.to_frame('value').reset_index().to_dict(orient='records'), many=True)
        return response.Response(serialised.data)
