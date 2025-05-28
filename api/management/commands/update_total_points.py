from django.core.management.base import BaseCommand
from django.db.models import Sum
from api.models import User, DrillResult

class Command(BaseCommand):
    help = 'Updates total_points for all students based on their DrillResult points'

    def handle(self, *args, **options):
        # Get all students
        students = User.objects.filter(role__name='student')
        updated_count = 0

        for student in students:
            # Calculate total points from DrillResult
            total_points = DrillResult.objects.filter(
                student=student
            ).aggregate(
                total=Sum('points')
            )['total'] or 0

            # Update student's total_points
            student.total_points = total_points
            student.save(update_fields=['total_points'])
            updated_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated {student.username}\'s total points to {total_points}'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated total points for {updated_count} students'
            )
        ) 