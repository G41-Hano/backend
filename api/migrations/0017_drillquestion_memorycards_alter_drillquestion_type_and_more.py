# Generated by Django 5.1.1 on 2025-05-16 12:45

import datetime
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_alter_drill_title_alter_passwordreset_expires_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='drillquestion',
            name='memoryCards',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AlterField(
            model_name='drillquestion',
            name='type',
            field=models.CharField(choices=[('M', 'Multiple Choice'), ('D', 'Drag and Drop'), ('F', 'Fill in the Blank'), ('G', 'Memory Game')], default='M', max_length=1),
        ),
        migrations.AlterField(
            model_name='passwordreset',
            name='expires_at',
            field=models.DateTimeField(default=datetime.datetime(2025, 5, 16, 13, 45, 36, 471111, tzinfo=datetime.timezone.utc)),
        ),
        migrations.CreateModel(
            name='MemoryGameResult',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('attempts', models.IntegerField(default=0)),
                ('matches', models.JSONField(default=list)),
                ('time_taken', models.FloatField()),
                ('score', models.FloatField()),
                ('drill_result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memory_game_results', to='api.drillresult')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memory_game_results', to='api.drillquestion')),
            ],
        ),
    ]
