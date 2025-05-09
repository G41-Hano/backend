# Generated by Django 5.2 on 2025-04-22 10:08

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_alter_classroom_id_alter_passwordreset_expires_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='class_code',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='passwordreset',
            name='expires_at',
            field=models.DateTimeField(default=datetime.datetime(2025, 4, 22, 11, 8, 38, 521562, tzinfo=datetime.timezone.utc)),
        ),
    ]
