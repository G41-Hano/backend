from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from api.models import User, QuestionResult

class Command(BaseCommand):
    help = 'Shows the number of correct answers for each student'

    def handle(self, *args, **options):
        # Get all students
        students = User.objects.filter(role__name='student')

        for student in students:
            # Count total questions attempted
            total_questions = QuestionResult.objects.filter(
                drill_result__student=student
            ).count()

            # Count correct answers
            correct_answers = QuestionResult.objects.filter(
                drill_result__student=student,
                is_correct=True
            ).count()

            # Calculate accuracy percentage
            accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0

            self.stdout.write(
                self.style.SUCCESS(
                    f'Student: {student.username}\n'
                    f'Total Questions Attempted: {total_questions}\n'
                    f'Correct Answers: {correct_answers}\n'
                    f'Accuracy: {accuracy:.2f}%\n'
                )
            ) 