from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
from .utils.encryption import encrypt, decrypt
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
import os

# Create your models here.

class Badge(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='badges/', null=True, blank=True)
    points_required = models.IntegerField(null=True, blank=True)
    drills_completed_required = models.IntegerField(null=True, blank=True)
    correct_answers_required = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['points_required']

class User(AbstractUser): # inherit AbstractUser
    email = models.EmailField(unique=True)  
    first_name_encrypted = models.BinaryField(null=True)
    last_name_encrypted = models.BinaryField(null=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    badges = models.ManyToManyField(Badge, related_name='users', blank=True)
    total_points_encrypted = models.BinaryField(null=True, blank=True)


    def save(self, *args, **kwargs):
        # encrypt first and last name before saving
        if self._state.adding: # checks if the instance is newly added
          if (self.first_name):
              self.first_name_encrypted = encrypt(self.first_name)
          if (self.last_name):
              self.last_name_encrypted = encrypt(self.last_name)
          if not self.total_points_encrypted:
              self.total_points_encrypted = encrypt(str(0))
        
        self.first_name = "***"
        self.last_name = "***"
        
        super().save(*args, **kwargs)

    @property
    def total_points(self):
        if self.total_points_encrypted:
            return int(decrypt(self.total_points_encrypted))
        return 0

    @total_points.setter
    def total_points(self, value):
        self.total_points_encrypted = encrypt(str(int(value)))

    def get_decrypted_first_name(self):
        if self.first_name_encrypted:
            return decrypt(self.first_name_encrypted)
        return None

    def get_decrypted_last_name(self):
        if self.last_name_encrypted:
            return decrypt(self.last_name_encrypted)
        return None

    def update_points_and_badges(self, points_to_add):
        """Update user's total points and check for new badges (latest attempt per drill only)"""
        # Calculate total points from only the latest attempt for each drill
        from collections import defaultdict
        drill_results = DrillResult.objects.filter(student=self)
        latest_by_drill = {}
        for result in drill_results:
            drill_id = result.drill_id
            if drill_id not in latest_by_drill or result.run_number > latest_by_drill[drill_id].run_number:
                latest_by_drill[drill_id] = result
        total_points = sum(r.points or 0 for r in latest_by_drill.values())

        # Store previous points for badge comparison
        previous_points = self.total_points
        # Update total points (encrypted)
        self.total_points = total_points
        self.save(update_fields=['total_points_encrypted'])

        # Get all badges that could be earned
        new_badges = set()

        # Check for point-based badges (including Pathfinder Prodigy)
        point_badges = Badge.objects.filter(
            points_required__isnull=False,
            drills_completed_required__isnull=True,
            correct_answers_required__isnull=True
        ).exclude(
            id__in=self.badges.values_list('id', flat=True)  # Exclude already earned badges
        )

        for badge in point_badges:
            # Pathfinder Prodigy: only award if points_required=100 and total_points is in [100, 1000)
            if badge.name == 'Pathfinder Prodigy':
                if badge.points_required == 100 and previous_points < 100 and 100 <= self.total_points < 1000:
                    new_badges.add(badge)
            elif previous_points < badge.points_required <= self.total_points:
                new_badges.add(badge)

        # Check for drill completion badges (like Vocabulary Rookie)
        completed_drills = DrillResult.objects.filter(
            student=self
        ).values('drill').distinct().count()

        drill_badges = Badge.objects.filter(
            drills_completed_required__isnull=False,
            points_required__isnull=True,
            correct_answers_required__isnull=True
        ).exclude(
            id__in=self.badges.values_list('id', flat=True)
        )

        for badge in drill_badges:
            if completed_drills >= badge.drills_completed_required:
                new_badges.add(badge)

        # Check for correct answers badges
        total_correct = QuestionResult.objects.filter(
            drill_result__student=self,
            is_correct=True
        ).count()

        correct_badges = Badge.objects.filter(
            correct_answers_required__isnull=False,
            points_required__isnull=True,
            drills_completed_required__isnull=True
        ).exclude(
            id__in=self.badges.values_list('id', flat=True)
        )

        for badge in correct_badges:
            if total_correct >= badge.correct_answers_required:
                new_badges.add(badge)

        # Award all new badges
        if new_badges:
            self.badges.add(*new_badges)
            # Create notifications for each new badge
            for badge in new_badges:
                Notification.objects.create(
                    recipient=self,
                    type='badge_earned',
                    message=f'Congratulations! You earned the {badge.name} badge!',
                    data={
                        'badge_id': badge.id,
                        'badge_name': badge.name,
                        'badge_description': badge.description,
                        'badge_image': badge.image.url if badge.image else None
                    }
                )

        return new_badges

    # award_first_drill_badge removed

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
    title = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    open_date = models.DateTimeField()  
    deadline = models.DateTimeField()   
    total_run = models.PositiveIntegerField(default=1)  # how many times the student will take the drill 
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='drills')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='drills')
    custom_wordlist = models.ForeignKey('WordList', on_delete=models.SET_NULL, null=True, blank=True, related_name='drills', default=None)
    wordlist_name = models.CharField(blank=True, help_text='Name of built-in wordlist used for this drill', max_length=100, null=True)
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    
    def create_with_questions(self, questions_input, request=None):
        """
        Create questions of appropriate subclass based on 'type' in questions_input.
        Supports choices via GenericRelation for SmartSelect/BlankBusters.
        """
        from django.contrib.contenttypes.models import ContentType
        type_to_model = {
        'M': SmartSelectQuestion,
        'F': BlankBustersQuestion,
        'D': SentenceBuilderQuestion,
        'P': PictureWordQuestion,
        'G': MemoryGameQuestion,
        }

        for q_data in questions_input or []:
            q_type = q_data.get('type') or q_data.get('drill_type')
            model_cls = type_to_model.get(q_type)
            if not model_cls:
                continue

            # Extract and remove choices for later processing
            choices_data = q_data.pop('choices', []) if isinstance(q_data, dict) else []

            # Handle media for Picture Word (P) and Memory Game (G) before creating the question
            if isinstance(q_data, dict):
                try:
                    # Picture Word: map media -> url
                    if q_type == 'P' and isinstance(q_data.get('pictureWord'), list):
                        processed_pictures = []
                        for picture in q_data.get('pictureWord', []):
                            if not isinstance(picture, dict):
                                processed_pictures.append(picture)
                                continue
                            media_key = picture.get('media')
                            if request and hasattr(request, 'FILES') and isinstance(media_key, str) and media_key in request.FILES:
                                f = request.FILES[media_key]
                                saved_url = None
                                if f.content_type.startswith('image/'):
                                    filename = f"vocabulary/images/{os.path.basename(f.name)}"
                                    saved_path = default_storage.save(filename, f)
                                    saved_url = default_storage.url(saved_path)
                                elif f.content_type.startswith('video/'):
                                    filename = f"vocabulary/videos/{os.path.basename(f.name)}"
                                    saved_path = default_storage.save(filename, f)
                                    saved_url = default_storage.url(saved_path)
                                if saved_url:
                                    picture['media'] = {'url': saved_url}
                            elif isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                                picture['media'] = {'url': media_key}
                            processed_pictures.append(picture)
                        q_data['pictureWord'] = processed_pictures

                    # Memory Game: map media -> content
                    if q_type == 'G' and isinstance(q_data.get('memoryCards'), list):
                        processed_cards = []
                        for card in q_data.get('memoryCards', []):
                            if not isinstance(card, dict):
                                processed_cards.append(card)
                                continue
                            media_key = card.get('media')
                            if request and hasattr(request, 'FILES') and isinstance(media_key, str) and media_key in request.FILES:
                                f = request.FILES[media_key]
                                saved_url = None
                                if f.content_type.startswith('image/'):
                                    filename = f"vocabulary/images/{os.path.basename(f.name)}"
                                    saved_path = default_storage.save(filename, f)
                                    saved_url = default_storage.url(saved_path)
                                elif f.content_type.startswith('video/'):
                                    filename = f"vocabulary/videos/{os.path.basename(f.name)}"
                                    saved_path = default_storage.save(filename, f)
                                    saved_url = default_storage.url(saved_path)
                                if saved_url:
                                    card['media'] = saved_url
                            elif isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                                card['media'] = media_key
                            processed_cards.append(card)
                        q_data['memoryCards'] = processed_cards
                except Exception:
                    pass

            # Handle question_media for Smart Select questions (M)
            if q_type == 'M' and isinstance(q_data, dict):
                media_key = q_data.get('question_media')
                if request and hasattr(request, 'FILES') and isinstance(media_key, str) and media_key in request.FILES:
                    # Handle uploaded file
                    f = request.FILES[media_key]
                    saved_url = None
                    if f.content_type.startswith('image/'):
                        filename = f"questions/images/{os.path.basename(f.name)}"
                        saved_path = default_storage.save(filename, f)
                        saved_url = default_storage.url(saved_path)
                    elif f.content_type.startswith('video/'):
                        filename = f"questions/videos/{os.path.basename(f.name)}"
                        saved_path = default_storage.save(filename, f)
                        saved_url = default_storage.url(saved_path)
                    if saved_url:
                        q_data['question_media'] = saved_url
                elif isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                    # Already a URL, keep it
                    q_data['question_media'] = media_key

            # Create question
            question_fields = {k: v for k, v in q_data.items() if k not in ['id', 'choices']}
            question = model_cls.objects.create(drill=self, **question_fields)
            print(f"Created {q_type} question with ID {question.id} for drill {self.id}")

            # Handle choices for SmartSelect/BlankBusters
            if q_type in ['M', 'F'] and choices_data:
                ct = ContentType.objects.get_for_model(question)
                for c_idx, choice in enumerate(choices_data):
                    # Handle optional media from request.FILES (key in 'media')
                    image = None
                    video = None
                    image_url = None
                    video_url = None
                    
                    media_key = choice.pop('media', None)
                    if request and media_key and isinstance(media_key, str) and hasattr(request, 'FILES') and media_key in request.FILES:
                        # Handle uploaded file
                        f = request.FILES[media_key]
                        if f.content_type.startswith('image/'):
                            image = f
                        elif f.content_type.startswith('video/'):
                            video = f
                    elif media_key and isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                        # Handle URL from wordlist - determine if it's image or video based on extension or path
                        lower_media = media_key.lower()
                        if any(ext in lower_media for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '/images/']):
                            image_url = media_key
                        elif any(ext in lower_media for ext in ['.mp4', '.webm', '.mov', '.avi', '/videos/']):
                            video_url = media_key

                    is_correct = False
                    if hasattr(question, 'answer') and question.answer is not None:
                        try:
                            is_correct = (c_idx == int(question.answer))
                        except (ValueError, TypeError):
                            is_correct = False

                    # Create choice with file or URL
                    drill_choice = DrillChoice.objects.create(
                        content_type=ct,
                        object_id=question.id,
                        text=choice.get('text', ''),
                        image=image,
                        video=video,
                        is_correct=is_correct,
                    )
                    
                    # If we have URLs, save them to the file fields
                    if image_url:
                        from django.core.files.base import ContentFile
                        import requests
                        try:
                            # For local URLs, just store the path
                            if image_url.startswith('/'):
                                drill_choice.image.name = image_url.lstrip('/')
                            else:
                                # For external URLs, download and save
                                response = requests.get(image_url, timeout=10)
                                if response.status_code == 200:
                                    filename = os.path.basename(image_url.split('?')[0])
                                    drill_choice.image.save(filename, ContentFile(response.content), save=False)
                        except Exception as e:
                            print(f"Error saving image URL: {e}")
                    
                    if video_url:
                        from django.core.files.base import ContentFile
                        import requests
                        try:
                            # For local URLs, just store the path
                            if video_url.startswith('/'):
                                drill_choice.video.name = video_url.lstrip('/')
                            else:
                                # For external URLs, download and save
                                response = requests.get(video_url, timeout=10)
                                if response.status_code == 200:
                                    filename = os.path.basename(video_url.split('?')[0])
                                    drill_choice.video.save(filename, ContentFile(response.content), save=False)
                        except Exception as e:
                            print(f"Error saving video URL: {e}")
                    
                    if image_url or video_url:
                        drill_choice.save()
        
        return self
        
    def update_with_questions(self, questions_input, request=None):
        """
        Upsert strategy:
        - Update existing questions by id and type
        - Create new questions not having an id
        - Delete questions removed from the payload
        Choices for M/F are fully replaced from the payload
        """
        from django.contrib.contenttypes.models import ContentType

        type_to_model = {
            'M': SmartSelectQuestion,
            'F': BlankBustersQuestion,
            'D': SentenceBuilderQuestion,
            'P': PictureWordQuestion,
            'G': MemoryGameQuestion,
        }

        # Track which IDs to keep per type
        kept_ids_by_type = {t: set() for t in type_to_model.keys()}

        for q_data in questions_input or []:
            if not isinstance(q_data, dict):
                continue

            q_type = q_data.get('type') or q_data.get('drill_type')
            model_cls = type_to_model.get(q_type)
            if not model_cls:
                continue

            # Extract choices for later (M/F only)
            choices_data = q_data.pop('choices', []) if isinstance(q_data, dict) else []

            # Preprocess media for P and G just like in create
            try:
                if q_type == 'P' and isinstance(q_data.get('pictureWord'), list):
                    processed_pictures = []
                    for picture in q_data.get('pictureWord', []):
                        if not isinstance(picture, dict):
                            processed_pictures.append(picture)
                            continue
                        media_key = picture.get('media')
                        if request and hasattr(request, 'FILES') and isinstance(media_key, str) and media_key in request.FILES:
                            f = request.FILES[media_key]
                            saved_url = None
                            if f.content_type.startswith('image/'):
                                filename = f"vocabulary/images/{os.path.basename(f.name)}"
                                saved_path = default_storage.save(filename, f)
                                saved_url = default_storage.url(saved_path)
                            elif f.content_type.startswith('video/'):
                                filename = f"vocabulary/videos/{os.path.basename(f.name)}"
                                saved_path = default_storage.save(filename, f)
                                saved_url = default_storage.url(saved_path)
                            if saved_url:
                                picture['media'] = {'url': saved_url}
                        elif isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                            picture['media'] = {'url': media_key}
                        processed_pictures.append(picture)
                    q_data['pictureWord'] = processed_pictures

                if q_type == 'G' and isinstance(q_data.get('memoryCards'), list):
                    processed_cards = []
                    for card in q_data.get('memoryCards', []):
                        if not isinstance(card, dict):
                            processed_cards.append(card)
                            continue
                        media_key = card.get('media')
                        if request and hasattr(request, 'FILES') and isinstance(media_key, str) and media_key in request.FILES:
                            f = request.FILES[media_key]
                            saved_url = None
                            if f.content_type.startswith('image/'):
                                filename = f"vocabulary/images/{os.path.basename(f.name)}"
                                saved_path = default_storage.save(filename, f)
                                saved_url = default_storage.url(saved_path)
                            elif f.content_type.startswith('video/'):
                                filename = f"vocabulary/videos/{os.path.basename(f.name)}"
                                saved_path = default_storage.save(filename, f)
                                saved_url = default_storage.url(saved_path)
                            if saved_url:
                                card['media'] = saved_url
                        elif isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                            card['media'] = media_key
                        processed_cards.append(card)
                    q_data['memoryCards'] = processed_cards
            except Exception:
                pass

            # Handle question_media for Smart Select questions (M)
            if q_type == 'M':
                media_key = q_data.get('question_media')
                if request and hasattr(request, 'FILES') and isinstance(media_key, str) and media_key in request.FILES:
                    # Handle uploaded file
                    f = request.FILES[media_key]
                    saved_url = None
                    if f.content_type.startswith('image/'):
                        filename = f"questions/images/{os.path.basename(f.name)}"
                        saved_path = default_storage.save(filename, f)
                        saved_url = default_storage.url(saved_path)
                    elif f.content_type.startswith('video/'):
                        filename = f"questions/videos/{os.path.basename(f.name)}"
                        saved_path = default_storage.save(filename, f)
                        saved_url = default_storage.url(saved_path)
                    if saved_url:
                        q_data['question_media'] = saved_url
                elif isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                    # Already a URL, keep it
                    q_data['question_media'] = media_key

            # Upsert question
            question_id = q_data.get('id')
            question_fields = {k: v for k, v in q_data.items() if k not in ['id', 'choices']}
            question = None
            if question_id is not None:
                question = model_cls.objects.filter(drill=self, id=question_id).first()

            if question:
                # Update existing
                for k, v in question_fields.items():
                    if hasattr(question, k):
                        setattr(question, k, v)
                question.save()
            else:
                # Create new
                question = model_cls.objects.create(drill=self, **question_fields)

            kept_ids_by_type[q_type].add(question.id)

            # Replace choices for M/F
            if q_type in ['M', 'F']:
                # Delete existing generic choices
                question.choices_generic.all().delete()
                ct = ContentType.objects.get_for_model(question)
                for c_idx, choice in enumerate(choices_data or []):
                    image = None
                    video = None
                    image_url = None
                    video_url = None
                    
                    media_key = choice.pop('media', None)
                    if request and media_key and isinstance(media_key, str) and hasattr(request, 'FILES') and media_key in request.FILES:
                        # Handle uploaded file
                        f = request.FILES[media_key]
                        if f.content_type.startswith('image/'):
                            image = f
                        elif f.content_type.startswith('video/'):
                            video = f
                    elif media_key and isinstance(media_key, str) and (media_key.startswith('http') or media_key.startswith('/')):
                        # Handle URL from wordlist
                        lower_media = media_key.lower()
                        if any(ext in lower_media for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '/images/']):
                            image_url = media_key
                        elif any(ext in lower_media for ext in ['.mp4', '.webm', '.mov', '.avi', '/videos/']):
                            video_url = media_key

                    is_correct = False
                    if hasattr(question, 'answer') and question.answer is not None:
                        try:
                            is_correct = (c_idx == int(question.answer))
                        except (ValueError, TypeError):
                            is_correct = False

                    drill_choice = DrillChoice.objects.create(
                        content_type=ct,
                        object_id=question.id,
                        text=choice.get('text', ''),
                        image=image,
                        video=video,
                        is_correct=is_correct,
                    )
                    
                    # If we have URLs, save them to the file fields
                    if image_url:
                        from django.core.files.base import ContentFile
                        import requests
                        try:
                            if image_url.startswith('/'):
                                drill_choice.image.name = image_url.lstrip('/')
                            else:
                                response = requests.get(image_url, timeout=10)
                                if response.status_code == 200:
                                    filename = os.path.basename(image_url.split('?')[0])
                                    drill_choice.image.save(filename, ContentFile(response.content), save=False)
                        except Exception as e:
                            print(f"Error saving image URL: {e}")
                    
                    if video_url:
                        from django.core.files.base import ContentFile
                        import requests
                        try:
                            if video_url.startswith('/'):
                                drill_choice.video.name = video_url.lstrip('/')
                            else:
                                response = requests.get(video_url, timeout=10)
                                if response.status_code == 200:
                                    filename = os.path.basename(video_url.split('?')[0])
                                    drill_choice.video.save(filename, ContentFile(response.content), save=False)
                        except Exception as e:
                            print(f"Error saving video URL: {e}")
                    
                    if image_url or video_url:
                        drill_choice.save()

        # Delete questions that were removed in payload
        for t, model_cls in type_to_model.items():
            existing = model_cls.objects.filter(drill=self).values_list('id', flat=True)
            to_delete = [qid for qid in existing if qid not in kept_ids_by_type[t]]
            if to_delete:
                model_cls.objects.filter(id__in=to_delete, drill=self).delete()

        return self

class DrillQuestionBase(models.Model): # abstract class will not be translated to a table in the database
    DRILL_TYPE = [
        ("M", "Smart Select"),
        ("F", "Blank Busters"),
        ("D", "Sentence Builder"),
        ("P", "Picture Word"),
        ("G", "Memory Game"),
    ]

    drill = models.ForeignKey(Drill, on_delete=models.CASCADE, related_name="%(class)s_questions")
    type = models.CharField(choices=DRILL_TYPE, default='S', max_length=1)

    text = models.CharField(max_length=200)
    word = models.CharField(max_length=255, blank=True, null=True)
    definition = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    # Abstract methods to be implemented by subclasses
    def check_answer(self, submitted_answer): raise NotImplementedError("Subclasses must implement this method")
    def compute_score(self, submitted_answer, meta=None): return None

    def save(self, *args, **kwargs):
        if hasattr(self, 'drill_type'):
            self.type = getattr(self, 'drill_type', self.type)
        super().save(*args, **kwargs)

class SmartSelectQuestion(DrillQuestionBase):
    drill_type = "M"
    answer = models.CharField(max_length=200, blank=True, null=True)  
    choices_generic = GenericRelation('DrillChoice', related_query_name='smartselect_question')
    question_media = models.URLField(max_length=500, blank=True, null=True) 

    def check_answer(self, submitted_answer):
        try:
            if submitted_answer is None or self.answer is None:
                return False
            return int(submitted_answer) == int(self.answer)
        except (ValueError, TypeError):
            return False

    def compute_score(self, submitted_answer, meta=None):
        # Base 100 minus 10 per incorrect attempt
        wrong_attempts = 0
        if isinstance(meta, dict):
            try:
                wrong_attempts = max(0, int(meta.get('wrong_attempts', 0)))
            except (ValueError, TypeError):
                wrong_attempts = 0
        return max(0.0, 100.0 - (wrong_attempts * 10.0))

class BlankBustersQuestion(DrillQuestionBase):
    drill_type = "F"
    letterChoices = models.JSONField(null=True, blank=True)  
    answer = models.CharField(max_length=200, blank=True, null=True)  
    pattern = models.CharField(max_length=200, blank=True, null=True)  
    hint = models.TextField(blank=True, null=True)  
    choices_generic = GenericRelation('DrillChoice', related_query_name='blankbusters_question')

    def check_answer(self, submitted_answer):
        # Support both index-based and text-based answers for backward compatibility
        if submitted_answer is None:
            return False
        # Index-based 
        try:
            submitted_index = int(submitted_answer)
            # When using index-based, derive correct index from self.answer if numeric, else from letterChoices is_correct
            try:
                correct_index = int(self.answer) if self.answer is not None else None
                if correct_index is not None:
                    return submitted_index == correct_index
            except (ValueError, TypeError):
                pass
        except (ValueError, TypeError):
            pass

        # Text-based compare (case-insensitive, trimmed)
        if isinstance(submitted_answer, str) and self.answer:
            return submitted_answer.strip().lower() == str(self.answer).strip().lower()
        return False

    def compute_score(self, submitted_answer, meta=None):
        wrong_attempts = 0
        if isinstance(meta, dict):
            try:
                wrong_attempts = max(0, int(meta.get('wrong_attempts', 0)))
            except (ValueError, TypeError):
                wrong_attempts = 0
        return max(0.0, 100.0 - (wrong_attempts * 10.0))

class SentenceBuilderQuestion(DrillQuestionBase):
    drill_type = "D"
    sentence = models.TextField(blank=True, null=True)  
    dragItems = models.JSONField(default=list, blank=True, null=True)  
    incorrectChoices = models.JSONField(default=list, blank=True, null=True)  

    def check_answer(self, submitted_answer):
        """
        Accepts any of the following formats and validates order strictly:
        - dict: {"0": 2, "1": 0} indices by blank position
        - list[int]: [2, 0] indices by blank position
        - list[str]: ["wordA", "wordB"] texts by blank position
        """
        try:
            if not self.dragItems:
                return False
            target_texts = [str(item.get('text', '')).strip().lower() for item in self.dragItems]
            num_targets = len(target_texts)

            # Dict form of indices
            if isinstance(submitted_answer, dict):
                built = []
                for i in range(num_targets):
                    sel = submitted_answer.get(str(i))
                    if sel is None:
                        return False
                    built.append(str(self.dragItems[int(sel)].get('text', '')).strip().lower())
                return built == target_texts

            # List form of indices
            if isinstance(submitted_answer, list) and all(isinstance(x, (int, str)) for x in submitted_answer):
                # If values are strings but numeric, treat as indices
                try:
                    idx_list = [int(x) for x in submitted_answer]
                    if len(idx_list) != num_targets:
                        return False
                    built = [str(self.dragItems[i].get('text', '')).strip().lower() for i in idx_list]
                    return built == target_texts
                except (ValueError, TypeError):
                    # Fallback to text comparison if not all indices
                    pass

            # List form of texts
            if isinstance(submitted_answer, list) and all(isinstance(x, str) for x in submitted_answer):
                texts = [str(x).strip().lower() for x in submitted_answer]
                if len(texts) != num_targets:
                    return False
                return texts == target_texts
        except Exception:
            return False
        return False

    def compute_score(self, submitted_answer, meta=None):
        wrong_attempts = 0
        if isinstance(meta, dict):
            try:
                wrong_attempts = max(0, int(meta.get('wrong_attempts', 0)))
            except (ValueError, TypeError):
                wrong_attempts = 0
        return max(0.0, 100.0 - (wrong_attempts * 10.0))

class PictureWordQuestion(DrillQuestionBase):
    drill_type = "P"
    pictureWord = models.JSONField(default=list, blank=True, null=True)  
    answer = models.CharField(max_length=200, blank=True, null=True)  

    def check_answer(self, submitted_answer):
        if not isinstance(submitted_answer, str) or not self.answer:
            return False
        return submitted_answer.strip().lower() == self.answer.strip().lower()

    def compute_score(self, submitted_answer, meta=None):
        wrong_attempts = 0
        if isinstance(meta, dict):
            try:
                wrong_attempts = max(0, int(meta.get('wrong_attempts', 0)))
            except (ValueError, TypeError):
                wrong_attempts = 0
        return max(0.0, 100.0 - (wrong_attempts * 10.0))

class MemoryGameQuestion(DrillQuestionBase):
    drill_type = "G"
    memoryCards = models.JSONField(default=list, blank=True, null=True) 

    def check_answer(self, submitted_answer):
        """
        For memory game, submitted_answer is expected to be a list of card IDs selected/matched.
        We consider it correct when all cards are matched without duplicates.
        """
        if not isinstance(submitted_answer, list) or not self.memoryCards:
            return False
        memory_card_ids = set()
        for card in self.memoryCards:
            cid = card.get('id')
            if cid is not None:
                memory_card_ids.add(str(cid))
        submitted_ids = [str(x) for x in submitted_answer]
        # no duplicates and covers all
        return len(submitted_ids) == len(set(submitted_ids)) and set(submitted_ids) == memory_card_ids

    # implementation of the abstract method since memory game has built-in scoring rule
    def compute_score(self, submitted_answer, meta=None):
        """
        Score = 100 - 5 * incorrect_pairings,
        where incorrect_pairings = max(0, attempts - expected_pairs)
        """
        attempts = 0
        if isinstance(meta, dict):
            try:
                attempts = int(meta.get('attempts', 0))
            except (ValueError, TypeError):
                attempts = 0
        expected_pairs = 0
        if isinstance(self.memoryCards, list):
            try:
                expected_pairs = max(0, int(len(self.memoryCards) // 2))
            except Exception:
                expected_pairs = 0
        incorrect_pairings = max(0, attempts - expected_pairs)
        return max(0.0, 100.0 - (incorrect_pairings * 5.0))

class DrillChoice(models.Model):
  id = models.AutoField(primary_key=True)
  # Legacy FK (kept for transition). New generic link supports subclass questions.
  content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
  object_id = models.PositiveIntegerField(null=True, blank=True)
  question_generic = GenericForeignKey('content_type', 'object_id')
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

    # New field to store the encrypted points
    _points_encrypted = models.BinaryField(null=True, blank=True) 

    # A temporary variable to hold the decrypted value for setting
    _points_decrypted_cache = None

    @property
    def points(self):
        """
        Returns the decrypted points value.
        """
        if self._points_decrypted_cache is not None:
            return self._points_decrypted_cache
        elif self._points_encrypted:
            try:
                self._points_decrypted_cache = float(decrypt(self._points_encrypted))
                return self._points_decrypted_cache
            except Exception as e:
                print(f"Error decrypting points for DrillResult {self.id}: {e}")
                return None
        return None
    
    @points.setter
    def points(self, value):
        """
        Sets the points value and encrypts it.
        """
        if value is not None:
            try:
                value = float(value)
            except (ValueError, TypeError):
                raise ValueError("Points must be a number.")
            
            self._points_decrypted_cache = value
            self._points_encrypted = encrypt(str(value))
        else:
            self._points_decrypted_cache = None
            self._points_encrypted = None

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # After saving, always sum all related QuestionResult points_awarded for this run
        total_points = self.question_results.aggregate(total=models.Sum('points_awarded'))['total'] or 0
        if self.points is None or self.points != total_points:
            self.points = total_points
            super().save(update_fields=['_points_encrypted'])
        
        # Update points and check for badges (always call this after points are updated)
        if self.points is not None:
            self.student.update_points_and_badges(self.points)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On initialization, if _points_encrypted exists, decrypt it to the cache
        if self._points_encrypted:
            try:
                self._points_decrypted_cache = float(decrypt(self._points_encrypted))
            except Exception as e:
                print(f"Error during __init__ decryption for DrillResult {self.id}: {e}")
                self._points_decrypted_cache = None

class QuestionResult(models.Model):
    id = models.AutoField(primary_key=True)
    drill_result = models.ForeignKey(DrillResult, on_delete=models.CASCADE, related_name='question_results')
    
    # New generic link to subclass questions
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    question_generic = GenericForeignKey('content_type', 'object_id')
    
    submitted_answer = models.JSONField(null=True, blank=True) # Store the student's submitted answer (flexible format)
    is_correct = models.BooleanField(default=False) # stores a student's result for a specific question within a drill run
    time_taken = models.FloatField(null=True, blank=True) # Time taken to answer this specific question (optional)
    submitted_at = models.DateTimeField(auto_now_add=True) # Timestamp of when this question was answered
    points_awarded = models.FloatField(default=0) # Points awarded for this specific question

    class Meta:
        unique_together = ('drill_result', 'content_type', 'object_id'); 

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
