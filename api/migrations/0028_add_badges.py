from django.db import migrations, models
import django.db.models.deletion

def create_initial_badges(apps, schema_editor):
    Badge = apps.get_model('api', 'Badge')
    
    # Create first drill badge
    Badge.objects.create(
        name="First Drill Completed",
        description="Completed your first drill!",
        image="badges/badge1.png",
        points_required=0,
        is_first_drill=True
    )
    
    # Create point-based badges
    Badge.objects.create(
        name="Bronze Achiever",
        description="Earned 30 points!",
        image="badges/badge2.png",
        points_required=30,
        is_first_drill=False
    )
    
    Badge.objects.create(
        name="Silver Achiever",
        description="Earned 50 points!",
        image="badges/badge3.png",
        points_required=50,
        is_first_drill=False
    )

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_alter_passwordreset_expires_at_questionresult'),
    ]

    operations = [
        migrations.CreateModel(
            name='Badge',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('image', models.ImageField(upload_to='badges/')),
                ('points_required', models.IntegerField(default=0)),
                ('is_first_drill', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['points_required'],
            },
        ),
        migrations.AddField(
            model_name='user',
            name='badges',
            field=models.ManyToManyField(blank=True, related_name='users', to='api.badge'),
        ),
        migrations.AddField(
            model_name='user',
            name='total_points',
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(create_initial_badges),
    ] 