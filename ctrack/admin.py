from django.contrib import admin

from ctrack import models

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('when', 'description', 'amount', 'is_split', 'category', 'account')

admin.site.register(models.Transaction, TransactionAdmin)
admin.site.register(models.SplitTransaction, TransactionAdmin)
