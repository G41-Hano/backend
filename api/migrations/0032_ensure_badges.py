from django.db import migrations, models

def ensure_badges(apps, schema_editor):
    Badge = apps.get_model('api', 'Badge')
    
    # Create badges if they don't exist
    badges_data = [
        {
            'name': "Pathfinder Prodigy",
            'description': "Completed your first vocabulary drill.",
            'image': "badges/badge1.png",
            'points_required': 0,
            'is_first_drill': True
        },
        {
            'name': "Vocabulary Rookie",
            'description': "Earned 10 points from drills!",
            'image': "badges/badge2.png",
            'points_required': 10,
            'is_first_drill': False
        },
        {
            'name': "Epic Achiever",
            'description': "Earned 30 points from drills!",
            'image': "badges/badge3.png",
            'points_required': 30,
            'is_first_drill': False
        },
        {
            'name': "The Noble Mind",
            'description': "Earned 50 points from drills!",
            'image': "badges/badge4.png",
            'points_required': 50,
            'is_first_drill': False
        },
        {
            'name': "Knowledge Master",
            'description': "Earned 100 points from drills!",
            'image': "badges/badge5.png",
            'points_required': 100,
            'is_first_drill': False
        }
    ]
    
    for badge_data in badges_data:
        Badge.objects.get_or_create(
            name=badge_data['name'],
            defaults=badge_data
        )

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0031_recreate_badges'),
    ]

    operations = [
        migrations.RunPython(ensure_badges),
    ] 