from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
from .utils.encryption import encrypt, decrypt
from django.conf import settings

# Create your models here.

class Badge(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='badges/', null=True, blank=True)
    points_required = models.IntegerField(null=True, blank=True)
    is_first_drill = models.BooleanField(default=False)  # Special badge for first drill completion
    drills_completed_required = models.IntegerField(null=True, blank=True)
    correct_answers_required = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['points_required']

class User(AbstractUser):
    first_name_encrypted = models.BinaryField(null=True)
    last_name_encrypted = models.BinaryField(null=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    badges = models.ManyToManyField(Badge, related_name='users', blank=True)
    total_points = models.IntegerField(default=0)  # Track total points across all drills

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

    def update_points_and_badges(self, points_to_add):
        """Update user's total points and check for new badges"""
        self.total_points += points_to_add
        self.save()
        
        # Check for point-based badges
        point_badges = Badge.objects.filter(
            points_required__lte=self.total_points,
            is_first_drill=False
        ).exclude(users=self)
        
        if point_badges.exists():
            self.badges.add(*point_badges)
            
        return point_badges

    def award_first_drill_badge(self):
        """Award badge for completing first drill"""
        first_drill_badge = Badge.objects.filter(is_first_drill=True).first()
        if first_drill_badge and not self.badges.filter(is_first_drill=True).exists():
            self.badges.add(first_drill_badge)
            return first_drill_badge
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
  is_correct = models.BooleanField(default=False) # marks which of the DrillChoice objects is the correct answer option used for Multiple Choice ('M') and Fill in the Blank ('F') questions

class DrillResult(models.Model):
    id = models.AutoField(primary_key=True)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drill_results')
    drill = models.ForeignKey(Drill, on_delete=models.CASCADE, related_name='drill_results')
    run_number = models.IntegerField(4)
    start_time = models.DateTimeField(auto_now_add=True)
    completion_time = models.DateTimeField()
    points = models.FloatField()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:  # Only process badges for new drill results
            # Check if this is the student's first drill
            if self.student.drill_results.count() == 1:
                first_drill_badge = self.student.award_first_drill_badge()
                if first_drill_badge:
                    # Create notification for first drill badge
                    Notification.objects.create(
                        recipient=self.student,
                        type='badge_earned',
                        message=f"Congratulations! You've earned the {first_drill_badge.name} badge!",
                        data={
                            'badge_id': first_drill_badge.id,
                            'badge_name': first_drill_badge.name,
                            'badge_description': first_drill_badge.description,
                            'badge_image': first_drill_badge.image.url if first_drill_badge.image else None
                        }
                    )
            
            # Update points and check for point-based badges
            point_badges = self.student.update_points_and_badges(self.points)
            
            # Create notifications for any new point-based badges
            for badge in point_badges:
                Notification.objects.create(
                    recipient=self.student,
                    type='badge_earned',
                    message=f"Congratulations! You've earned the {badge.name} badge!",
                    data={
                        'badge_id': badge.id,
                        'badge_name': badge.name,
                        'badge_description': badge.description,
                        'badge_image': badge.image.url if badge.image else None
                    }
                )

class MemoryGameResult(models.Model):
    id = models.AutoField(primary_key=True)
    drill_result = models.ForeignKey(DrillResult, on_delete=models.CASCADE, related_name='memory_game_results')
    question = models.ForeignKey(DrillQuestion, on_delete=models.CASCADE, related_name='memory_game_results')
    attempts = models.IntegerField(default=0)
    matches = models.JSONField(default=list)  # Store matched pairs
    time_taken = models.FloatField()  # Time taken in seconds
    score = models.FloatField()  # Score based on attempts and time

class QuestionResult(models.Model):
    id = models.AutoField(primary_key=True)
    drill_result = models.ForeignKey(DrillResult, on_delete=models.CASCADE, related_name='question_results')
    question = models.ForeignKey(DrillQuestion, on_delete=models.CASCADE, related_name='question_results')
    submitted_answer = models.JSONField(null=True, blank=True) # Store the student's submitted answer (flexible format)
    is_correct = models.BooleanField(default=False) # stores a student's result for a specific question within a drill run
    time_taken = models.FloatField(null=True, blank=True) # Time taken to answer this specific question (optional)
    submitted_at = models.DateTimeField(auto_now_add=True) # Timestamp of when this question was answered
    points_awarded = models.FloatField(default=0) # Points awarded for this specific question

    class Meta:
        unique_together = ('drill_result', 'question'); # Ensure a student only has one result per question per drill run

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
        ('transfer_rejected', 'Transfer Rejected'),
        ('student_added', 'Student Added to Classroom'),
        ('student_removed', 'Student Removed from Classroom'),
        ('badge_earned', 'Badge Earned')
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
