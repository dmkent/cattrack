from django.contrib import admin

from ctrack import models

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('when', 'description', 'amount', 'is_split', 'category', 'account')

admin.site.register(models.Transaction, TransactionAdmin)
admin.site.register(models.SplitTransaction, TransactionAdmin)
admin.site.register(models.PeriodDefinition)
admin.site.register(models.Bill)
admin.site.register(models.RecurringPayment)
admin.site.register(models.Category)
