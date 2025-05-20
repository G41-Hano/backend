from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_classroom_is_archived_alter_passwordreset_expires_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransferRequest',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reason', models.TextField(blank=True, null=True)),
                ('from_classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_transfers', to='api.classroom')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_requests_made', to='api.user')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_requests', to='api.user')),
                ('to_classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming_transfers', to='api.classroom')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('type', models.CharField(choices=[('student_transfer', 'Student Transfer Request'), ('transfer_approved', 'Transfer Approved'), ('transfer_rejected', 'Transfer Rejected')], max_length=20)),
                ('message', models.TextField()),
                ('data', models.JSONField(default=dict)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='api.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ] 