# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-12-23 22:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ctrack', '0007_auto_20171223_2209'),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('valid_from', models.DateField()),
                ('valid_to', models.DateField()),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ctrack.Category')),
            ],
        ),
    ]
