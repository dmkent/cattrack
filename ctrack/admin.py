from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from ctrack import models

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('when', 'description', 'amount', 'is_split', 'category', 'account')
    list_filter = ("category", "account")

class CategoryGroupListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('category group')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'group'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        cats = model_admin.get_queryset(request).values("name")
        names = sorted(set(cat['name'].split(' - ')[0] for cat in cats))
        print(names)
        return [(name, name) for name in names]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        if self.value() is None:
            return queryset
        return queryset.filter(name__startswith=self.value())

class CatecgoryAdmin(admin.ModelAdmin):
    list_filter = (CategoryGroupListFilter,)

admin.site.register(models.Account)
admin.site.register(models.Transaction, TransactionAdmin)
admin.site.register(models.SplitTransaction, TransactionAdmin)
admin.site.register(models.PeriodDefinition)
admin.site.register(models.Bill)
admin.site.register(models.RecurringPayment)
admin.site.register(models.BillPdfScraperConfig)
admin.site.register(models.Category, CatecgoryAdmin)
admin.site.register(models.BalancePoint)
admin.site.register(models.BudgetEntry)