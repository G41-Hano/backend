from django.core.management.base import BaseCommand
from django.db.models import Count
from api.models import User, QuestionResult, Badge, Notification

class Command(BaseCommand):
    help = 'Awards Epic Achiever badge to students with 10 or more correct answers'

    def handle(self, *args, **options):
        # Get the Epic Achiever badge
        try:
            epic_achiever_badge = Badge.objects.get(name='Epic Achiever')
        except Badge.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Epic Achiever badge not found in database')
            )
            return

        # Get all students
        students = User.objects.filter(role__name='student')
        awarded_count = 0

        for student in students:
            # Count correct answers
            correct_answers = QuestionResult.objects.filter(
                drill_result__student=student,
                is_correct=True
            ).count()

            # Check if student has earned the badge
            if correct_answers >= epic_achiever_badge.correct_answers_required:
                # Check if student already has the badge
                if not student.badges.filter(id=epic_achiever_badge.id).exists():
                    # Award the badge
                    student.badges.add(epic_achiever_badge)
                    
                    # Create notification
                    Notification.objects.create(
                        recipient=student,
                        type='badge_earned',
                        message=f'Congratulations! You earned the Epic Achiever badge for getting {correct_answers} correct answers!',
                        data={
                            'badge_id': epic_achiever_badge.id,
                            'badge_name': epic_achiever_badge.name,
                            'badge_description': epic_achiever_badge.description,
                            'badge_image': epic_achiever_badge.image.url if epic_achiever_badge.image else None
                        }
                    )
                    
                    awarded_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Awarded Epic Achiever badge to {student.username} '
                            f'(Correct Answers: {correct_answers})'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'{student.username} already has the Epic Achiever badge '
                            f'(Correct Answers: {correct_answers})'
                        )
                    )
            else:
                self.stdout.write(
                    f'{student.username}: {correct_answers} correct answers '
                    f'(needs {epic_achiever_badge.correct_answers_required})'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully awarded Epic Achiever badge to {awarded_count} new students'
            )
        ) 