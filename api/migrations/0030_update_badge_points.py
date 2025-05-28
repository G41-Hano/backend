from django.db import migrations, models

def update_badge_points(apps, schema_editor):
    Badge = apps.get_model('api', 'Badge')
    
    # Update existing badges
    badge2 = Badge.objects.get(name="Bronze Achiever")
    badge2.points_required = 10
    badge2.description = "Earned 10 points!"
    badge2.save()
    
    badge3 = Badge.objects.get(name="Silver Achiever")
    badge3.points_required = 30
    badge3.description = "Earned 30 points!"
    badge3.save()
    
    # Add new badges
    Badge.objects.create(
        name="Gold Achiever",
        description="Earned 50 points!",
        image="badges/badge4.png",
        points_required=50,
        is_first_drill=False
    )
    
    Badge.objects.create(
        name="Platinum Achiever",
        description="Earned 100 points!",
        image="badges/badge5.png",
        points_required=100,
        is_first_drill=False
    )

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0029_merge_20250525_1237'),
    ]

    operations = [
        migrations.RunPython(update_badge_points),
    ] 