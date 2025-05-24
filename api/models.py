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
  avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

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

class Classroom(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='classrooms')
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='enrolled_classrooms', blank=True)
    class_code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    is_hidden = models.BooleanField(default=False)  # Hidden state
    is_archived = models.BooleanField(default=False)  # Archived state
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.class_code:
            self.class_code = self.generate_class_code()
        super().save(*args, **kwargs)

    def generate_class_code(self):
        import random
        import string
        
        # Generate a random 6-character code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Check if code already exists
        while Classroom.objects.filter(class_code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        return code

    class Meta:
        ordering = ['-created_at']  # Order by creation date


class WordList(models.Model):
  id = models.AutoField(primary_key=True)
  name = models.CharField(max_length=20)
  description = models.CharField(max_length=200)
  created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_word_lists', blank=True, null=True)

class Vocabulary(models.Model):
  word = models.CharField(max_length=20)
  definition = models.CharField(max_length=200)
  image_url = models.URLField(max_length=500, null=True) # null=True for now since there is no image/video storage yet
  video_url = models.URLField(max_length=500, null=True) # null=True for now since there is no image/video storage yet
  # FILE FIELD for IMAGE or VIDEO
  list = models.ForeignKey(WordList, on_delete=models.CASCADE, related_name="words")
   
class Drill(models.Model):
  id = models.AutoField(primary_key=True)
  title = models.TextField(max_length=50)
  description = models.TextField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  deadline = models.DateTimeField()
  total_run = models.PositiveIntegerField(default=1)  # how many times the student will take the drill 
  created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drills')
  classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='drills')
  custom_wordlist = models.ForeignKey('WordList', on_delete=models.SET_NULL, null=True, blank=True, related_name='drills', default=None)
  STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
  ]
  status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

class DrillQuestion(models.Model):
  TYPE = [
    ("M","Multiple Choice"),
    ("D","Drag and Drop"),
    ("F","Fill in the Blank"),
    ("G","Memory Game"),  
    ("P","Picture Word")
  ]

  id = models.AutoField(primary_key=True)
  text = models.TextField(max_length=200)
  type = models.CharField(choices=TYPE, default='M', max_length=1)
  drill = models.ForeignKey(Drill, on_delete=models.CASCADE, related_name='questions')
  dragItems = models.JSONField(default=list, blank=True, null=True)
  dropZones = models.JSONField(default=list, blank=True, null=True)
  blankPosition = models.IntegerField(blank=True, null=True)
  memoryCards = models.JSONField(default=list, blank=True, null=True)  # New field for memory game cards
  pictureWord = models.JSONField(default=list, blank=True, null=True)  # New field for picture word questions
  answer = models.TextField(max_length=200, blank=True, null=True)  # Add answer field

  #fields for learning content drill
  story_title = models.CharField(max_length=100, blank=True, null=True)
  story_context = models.TextField(blank=True, null=True)
  sign_language_instructions = models.TextField(blank=True, null=True)

class DrillChoice(models.Model):
  id = models.AutoField(primary_key=True)
  question = models.ForeignKey(DrillQuestion, on_delete=models.CASCADE, related_name='choices')
  text = models.CharField(max_length=200, blank=True)
  image = models.ImageField(upload_to='drill_choices/images/', null=True, blank=True)
  video = models.FileField(upload_to='drill_choices/videos/', null=True, blank=True)
  is_correct = models.BooleanField(default=False)

class DrillResult(models.Model):
  id = models.AutoField(primary_key=True)
  student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drill_results')
  drill = models.ForeignKey(Drill, on_delete=models.CASCADE, related_name='drill_results')
  run_number = models.IntegerField(4)
  start_time = models.DateTimeField(auto_now_add=True)
  completion_time = models.DateTimeField()
  points = models.FloatField()

class MemoryGameResult(models.Model):
    id = models.AutoField(primary_key=True)
    drill_result = models.ForeignKey(DrillResult, on_delete=models.CASCADE, related_name='memory_game_results')
    question = models.ForeignKey(DrillQuestion, on_delete=models.CASCADE, related_name='memory_game_results')
    attempts = models.IntegerField(default=0)
    matches = models.JSONField(default=list)  # Store matched pairs
    time_taken = models.FloatField()  # Time taken in seconds
    score = models.FloatField()  # Score based on attempts and time
  
#Transfer Request
class TransferRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ]
    
    id = models.AutoField(primary_key=True)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transfer_requests')
    from_classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='incoming_transfers')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transfer_requests_made')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Transfer request for {self.student.username} from {self.from_classroom.name} to {self.to_classroom.name}"

    class Meta:
        ordering = ['-created_at']

#Notification

class Notification(models.Model):
    TYPE_CHOICES = [
        ('student_transfer', 'Student Transfer Request'),
        ('transfer_approved', 'Transfer Approved'),
        ('transfer_rejected', 'Transfer Rejected')
    ]
    
    id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    data = models.JSONField(default=dict)  # Additional data related to the notification
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.type}"

    class Meta:
        ordering = ['-created_at']
