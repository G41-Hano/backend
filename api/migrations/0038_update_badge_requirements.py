from django.db import migrations, models

def update_badges(apps, schema_editor):
    Badge = apps.get_model('api', 'Badge')
    updates = [
        {
            'name': 'Pathfinder Prodigy',
            'description': 'You have earned 100 points on your First Drill!',
            'image': 'badges/badge1.png',
            'points_required': 100,
            'is_first_drill': True,
            'drills_completed_required': None,
            'correct_answers_required': None,
        },
        {
            'name': 'Vocabulary Rookie',
            'description': 'Awesome! You have completed 3 Drills!',
            'image': 'badges/badge2.png',
            'points_required': None,
            'is_first_drill': False,
            'drills_completed_required': 3,
            'correct_answers_required': None,
        },
        {
            'name': 'Epic Achiever',
            'description': 'Amazing! You have 10 correct answers!',
            'image': 'badges/badge3.png',
            'points_required': None,
            'is_first_drill': False,
            'drills_completed_required': None,
            'correct_answers_required': 10,
        },
        {
            'name': 'The Noble Mind',
            'description': 'Astonishing! You have completed 5 Drills!',
            'image': 'badges/badge4.png',
            'points_required': None,
            'is_first_drill': False,
            'drills_completed_required': 5,
            'correct_answers_required': None,
        },
        {
            'name': 'Knowledge Master',
            'description': 'Extraordinary! You have earned 1000 points!',
            'image': 'badges/badge5.png',
            'points_required': 1000,
            'is_first_drill': False,
            'drills_completed_required': None,
            'correct_answers_required': None,
        },
    ]
    for data in updates:
        Badge.objects.filter(name=data['name']).update(
            description=data['description'],
            image=data['image'],
            points_required=data['points_required'],
            is_first_drill=data['is_first_drill'],
            drills_completed_required=data['drills_completed_required'],
            correct_answers_required=data['correct_answers_required'],
        )

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0036_drill_custom_wordlist_alter_passwordreset_expires_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='badge',
            name='points_required',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='badge',
            name='drills_completed_required',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='badge',
            name='correct_answers_required',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(update_badges),
    ]
