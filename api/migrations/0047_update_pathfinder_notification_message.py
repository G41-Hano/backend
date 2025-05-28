from django.db import migrations

def update_notification_message(apps, schema_editor):
    User = apps.get_model('api', 'User')
    Badge = apps.get_model('api', 'Badge')
    Notification = apps.get_model('api', 'Notification')
    
    # Get the Pathfinder Prodigy badge
    pathfinder_badge = Badge.objects.get(name='Pathfinder Prodigy')
    
    # Find all students who have the badge
    students_with_badge = User.objects.filter(badges=pathfinder_badge)
    
    # Update the notification message for each student
    for student in students_with_badge:
        # Get the most recent badge notification for this student
        notification = Notification.objects.filter(
            recipient=student,
            type='badge_earned',
            data__badge_id=pathfinder_badge.id
        ).order_by('-created_at').first()
        
        if notification:
            notification.message = 'Congratulations! You have earned the Pathfinder Prodigy badge!'
            notification.save()

def reverse_update_notification_message(apps, schema_editor):
    # No need to reverse this migration as it only updates messages
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0046_alter_passwordreset_expires_at'),
    ]

    operations = [
        migrations.RunPython(update_notification_message, reverse_update_notification_message),
    ] 