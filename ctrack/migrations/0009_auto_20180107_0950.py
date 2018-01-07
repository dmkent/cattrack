# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-01-07 09:50
from __future__ import unicode_literals

import ctrack.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ctrack', '0008_budgetentry'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='budgetentry',
            options={'ordering': ['-valid_to'], 'verbose_name_plural': 'budget entries'},
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['name'], 'verbose_name_plural': 'categories'},
        ),
        migrations.AlterModelOptions(
            name='transaction',
            options={'ordering': ['-when']},
        ),
        migrations.AddField(
            model_name='budgetentry',
            name='categories',
            field=models.ManyToManyField(to='ctrack.Category'),
        ),
        migrations.AlterField(
            model_name='budgetentry',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='old_categories', to='ctrack.Category'),
        ),
        migrations.AlterField(
            model_name='budgetentry',
            name='valid_from',
            field=models.DateField(default=ctrack.models.current_year_start),
        ),
        migrations.AlterField(
            model_name='budgetentry',
            name='valid_to',
            field=models.DateField(default=ctrack.models.current_year_end),
        ),
    ]
