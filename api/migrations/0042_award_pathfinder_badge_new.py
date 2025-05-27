from django.db import migrations

def award_pathfinder_badge(apps, schema_editor):
    User = apps.get_model('api', 'User')
    Badge = apps.get_model('api', 'Badge')
    Notification = apps.get_model('api', 'Notification')
    
    # Get the Pathfinder Prodigy badge
    pathfinder_badge = Badge.objects.get(name='Pathfinder Prodigy')
    
    # Find all students who:
    # 1. Have between 100 and 1000 points
    # 2. Don't already have the badge
    eligible_students = User.objects.filter(
        total_points__gte=100,
        total_points__lt=1000,
        role__name='student'
    ).exclude(
        badges=pathfinder_badge
    )
    
    # Award the badge to eligible students
    for student in eligible_students:
        student.badges.add(pathfinder_badge)
        # Create notification for the badge
        Notification.objects.create(
            recipient=student,
            type='badge_earned',
            message='Congratulations! You have earned the Pathfinder Prodigy badge!',
            data={
                'badge_id': pathfinder_badge.id,
                'badge_name': pathfinder_badge.name,
                'badge_description': pathfinder_badge.description,
                'badge_image': pathfinder_badge.image.url if pathfinder_badge.image else None
            }
        )

def reverse_award_pathfinder_badge(apps, schema_editor):
    # No need to reverse this migration as it only awards badges
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0041_award_pathfinder_badge'),
    ]

    operations = [
        migrations.RunPython(award_pathfinder_badge, reverse_award_pathfinder_badge),
    ] 