from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
from .utils.encryption import encrypt, decrypt
from django.conf import settings

# Create your models here.

class User(AbstractUser):
  first_name_encrypted = models.BinaryField(null=True)
  last_name_encrypted = models.BinaryField(null=True)

  def save(self, *args, **kwargs):
    # encrypt first and last name before saving
    if (self.first_name):
      self.first_name_encrypted = encrypt(self.first_name)
    if (self.last_name):
      self.last_name_encrypted = encrypt(self.last_name)
    
    self.first_name = "***"
    self.last_name = "***"
    
    super().save(*args, **kwargs)

  def get_decrypted_first_name(self):
    if self.first_name_encrypted:
      return decrypt(self.first_name_encrypted)
    return None

  def get_decrypted_last_name(self):
    if self.last_name_encrypted:
      return decrypt(self.last_name_encrypted)
    return None


class Role(models.Model):
  STUDENT = 'student'
  TEACHER = 'teacher'

  ROLE_CHOICES = [
    (STUDENT, 'Student'),
    (TEACHER, 'Teacher'),
  ]

  user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role")
  name = models.CharField(max_length=10, choices=ROLE_CHOICES, default=STUDENT)

  def __str__(self):
    return self.name

class PasswordReset(models.Model):
  email = models.EmailField()
  token = models.CharField(max_length=100)
  created_at = models.DateTimeField(auto_now_add=True)
  expires_at = models.DateTimeField(default=timezone.now() + timedelta(hours=1))  # Default set to 1 hour from now

  def is_expired(self):
    return timezone.now() > self.expires_at

  def save(self, *args, **kwargs):
    if not self.expires_at:
      self.expires_at = timezone.now() + timedelta(hours=1)
    super().save(*args, **kwargs)

