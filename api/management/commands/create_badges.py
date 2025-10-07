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
                'points_required': 100
            },
            {
                'name': "Vocabulary Rookie",
                'description': "Completed 3 drills.",
                'image': "badges/badge2.png",
                'points_required': None,
                'drills_completed_required': 3
            },
            {
                'name': "Epic Achiever",
                'description': "Reached 2000+ points from drills!",
                'image': "badges/badge3.png",
                'points_required': 2000
            },
            {
                'name': "The Noble Mind",
                'description': "Completed 5 drills.",
                'image': "badges/badge4.png",
                'points_required': None,
                'drills_completed_required': 5
            },
            {
                'name': "Knowledge Master",
                'description': "Reached 1000+ points from drills!",
                'image': "badges/badge5.png",
                'points_required': 1000
            }
        ]

        # Create or update badges 
        for badge_data in badges_data:
            badge, created = Badge.objects.update_or_create(
                name=badge_data['name'],
                defaults=badge_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created badge: {badge.name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Updated badge: {badge.name}'))

        # Verify badges were created
        badge_count = Badge.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Total badges in database: {badge_count}')) 