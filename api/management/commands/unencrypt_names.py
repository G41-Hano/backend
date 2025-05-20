from django.core.management.base import BaseCommand
from api.models import User
from api.utils.encryption import decrypt

class Command(BaseCommand):
    help = 'Unencrypt first and last names in the database'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        for user in users:
            if user.first_name_encrypted:
                user.first_name = decrypt(user.first_name_encrypted)
            if user.last_name_encrypted:
                user.last_name = decrypt(user.last_name_encrypted)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Unencrypted names for user {user.username}'))
