from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ctrack", "0018_recurringpayment_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="categorisormodel",
            name="exclusion_summary",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="categorisormodel",
            name="training_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="categorisormodel",
            name="training_metrics",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
