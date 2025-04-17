from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import PasswordReset

class Command(BaseCommand):
    help = 'Delete expired password reset tokens'

    def handle(self, *args, **kwargs):
        expired_tokens = PasswordReset.objects.filter(expires_at__lt=timezone.now())
        expired_count = expired_tokens.count()

        if expired_count > 0:
            expired_tokens.delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {expired_count} expired token(s).'))
        else:
            self.stdout.write(self.style.SUCCESS('No expired tokens found.'))
