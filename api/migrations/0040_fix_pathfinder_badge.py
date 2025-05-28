from django.db import migrations, models

def fix_pathfinder_badge(apps, schema_editor):
    Badge = apps.get_model('api', 'Badge')
    # Delete any existing Pathfinder Prodigy badges
    Badge.objects.filter(name='Pathfinder Prodigy').delete()
    # Create a new one with correct settings
    Badge.objects.create(
        name='Pathfinder Prodigy',
        description='Great! You have earned 100 points!',
        image='badges/badge1.png',
        points_required=100,
        is_first_drill=False,
        drills_completed_required=None,
        correct_answers_required=None
    )

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0039_alter_badge_image_alter_passwordreset_expires_at'),
    ]

    operations = [
        migrations.RunPython(fix_pathfinder_badge),
    ]