from django.db import migrations

def award_pathfinder_badge(apps, schema_editor):
    User = apps.get_model('api', 'User')
    Badge = apps.get_model('api', 'Badge')
    
    # Get the Pathfinder Prodigy badge
    pathfinder_badge = Badge.objects.filter(
        name='Pathfinder Prodigy',
        is_first_drill=False
    ).first()
    
    if pathfinder_badge:
        # Find all students with 100+ points who don't have the badge
        eligible_students = User.objects.filter(
            total_points__gte=100,
            total_points__lt=200
        ).exclude(
            badges=pathfinder_badge
        )
        
        # Award the badge to all eligible students
        for student in eligible_students:
            student.badges.add(pathfinder_badge)
            print(f"Awarded Pathfinder Prodigy badge to student {student.username} with {student.total_points} points")

def reverse_award_pathfinder_badge(apps, schema_editor):
    # No need to reverse this migration
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0040_fix_pathfinder_badge'),
    ]

    operations = [
        migrations.RunPython(award_pathfinder_badge, reverse_award_pathfinder_badge),
    ] 