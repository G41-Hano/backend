from django.db import migrations, models

def recreate_badges(apps, schema_editor):
    Badge = apps.get_model('api', 'Badge')
    
    # Clear existing badges
    Badge.objects.all().delete()
    
    # Create first drill badge
    Badge.objects.create(
        name="Pathfinder Prodigy",
        description="Completed your first vocabulary drill.",
        image="badges/badge1.png",
        points_required=0,
        is_first_drill=True
    )
    
    # Create point-based badges
    Badge.objects.create(
        name="Vocabulary Rookie",
        description="Earned 10 points from drills!",
        image="badges/badge2.png",
        points_required=10,
        is_first_drill=False
    )
    
    Badge.objects.create(
        name="Epic Achiever",
        description="Earned 30 points from drills!",
        image="badges/badge3.png",
        points_required=30,
        is_first_drill=False
    )
    
    Badge.objects.create(
        name="The Noble Mind",
        description="Earned 50 points from drills!",
        image="badges/badge4.png",
        points_required=50,
        is_first_drill=False
    )
    
    Badge.objects.create(
        name="Knowledge Master",
        description="Earned 100 points from drills!",
        image="badges/badge5.png",
        points_required=100,
        is_first_drill=False
    )

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0030_update_badge_points'),
    ]

    operations = [
        migrations.RunPython(recreate_badges),
    ] 