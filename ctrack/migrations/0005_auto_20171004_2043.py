# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-10-04 20:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ctrack', '0004_auto_20170930_0011'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='balancepoint',
            options={'get_latest_by': 'ref_date'},
        ),
        migrations.AddField(
            model_name='bill',
            name='issued_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
