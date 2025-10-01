from django.core.management.base import BaseCommand
from api.models import Badge

class Command(BaseCommand):
    help = 'Creates or updates badges in the database'

    def handle(self, *args, **kwargs):
        badges_data = [
            {
                'name': "Pathfinder Prodigy",
                'description': "Completed your first vocabulary drill.",
                'image': "badges/badge1.png",
                'points_required': None,
                'is_first_drill': True
            },
            {
                'name': "Vocabulary Rookie",
                'description': "Completed 3 drills.",
                'image': "badges/badge2.png",
                'points_required': None,
                'is_first_drill': False,
                'drills_completed_required': 3
            },
            {
                'name': "Epic Achiever",
                'description': "Reached 1000+ points from drills!",
                'image': "badges/badge3.png",
                'points_required': 1000,
                'is_first_drill': False
            },
            {
                'name': "The Noble Mind",
                'description': "Completed 5 drills.",
                'image': "badges/badge4.png",
                'points_required': None,
                'is_first_drill': False,
                'drills_completed_required': 5
            },
            {
                'name': "Knowledge Master",
                'description': "Reached 500+ points from drills!",
                'image': "badges/badge5.png",
                'points_required': 500,
                'is_first_drill': False
            }
        ]

        # First, clear existing badges
        Badge.objects.all().delete()
        self.stdout.write('Cleared existing badges')

        # Create new badges
        for badge_data in badges_data:
            badge, created = Badge.objects.get_or_create(
                name=badge_data['name'],
                defaults=badge_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created badge: {badge.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Badge already exists: {badge.name}'))

        # Verify badges were created
        badge_count = Badge.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Total badges in database: {badge_count}')) 