from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from collections import Counter
import os

# Serializers that convert the Django Object to JSON, and vice versa

class CustomTokenSerializer(TokenObtainPairSerializer):
  @classmethod
  def get_token(cls, user):
    token = super().get_token(user)

    # Add custom claims
    token['first_name'] = user.get_decrypted_first_name()
    token['last_name'] = user.get_decrypted_last_name()
    token['role'] = user.role.name
    # ...

    return token

class BadgeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    is_earned = serializers.SerializerMethodField()
    earned_at = serializers.SerializerMethodField()
    requirement_type = serializers.SerializerMethodField()
    requirement_value = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        fields = [
            'id', 'name', 'description', 'image', 'image_url',
            'points_required', 'drills_completed_required',
            'correct_answers_required', 'progress', 'is_earned', 'earned_at',
            'requirement_type', 'requirement_value'
        ]

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_progress(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        user = request.user
        if obj.points_required is not None:
            return min(100, (user.total_points / obj.points_required * 100))
        elif obj.drills_completed_required is not None:
            completed_drills = DrillResult.objects.filter(student=user).count()
            return min(100, (completed_drills / obj.drills_completed_required * 100))
        elif obj.correct_answers_required is not None:
            correct_answers = QuestionResult.objects.filter(
                drill_result__student=user,
                is_correct=True
            ).count()
            return min(100, (correct_answers / obj.correct_answers_required * 100))
        return None

    def get_is_earned(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.users.filter(id=request.user.id).exists()

    def get_earned_at(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            return obj.users.through.objects.filter(
                user=request.user,
                badge=obj
            ).first().created_at
        except:
            return None

    def get_requirement_type(self, obj):
        if obj.points_required is not None:
            return 'points'
        elif obj.drills_completed_required is not None:
            return 'drills_completed'
        elif obj.correct_answers_required is not None:
            return 'correct_answers'
        return None

    def get_requirement_value(self, obj):
        if obj.points_required is not None:
            return obj.points_required
        elif obj.drills_completed_required is not None:
            return obj.drills_completed_required
        elif obj.correct_answers_required is not None:
            return obj.correct_answers_required
        return None

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="role.name", read_only=True)  # Include role in response
    role_input = serializers.ChoiceField(choices=Role.ROLE_CHOICES, write_only=True, required=True)
    badges = BadgeSerializer(many=True, read_only=True)
    total_points = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "password", "first_name", "last_name", "email", "role", "role_input", "first_name_encrypted", "last_name_encrypted", "avatar", "badges", "total_points"]
        extra_kwargs = {"password": {"write_only": True},
                    "first_name_encrypted": {"read_only": True},
                    "last_name_encrypted": {"read_only": True},
                    }     # exclude this data when it is requested

    def create(self, validated_data):
        role_name = validated_data.pop("role_input")          # Extract role from data
        user = User.objects.create_user(**validated_data)     # Create user object (password already hashed)
        Role.objects.create(user=user, name=role_name)        # Create role object (to know if user is student or teacher)
        return user
  
    def to_representation(self, instance):
        """Decrypt first and last name for output"""
        ret = super().to_representation(instance)

        # Decrypt first name using the model method
        try:
            ret['first_name'] = instance.get_decrypted_first_name()
        except Exception as e:
            ret['first_name'] = "ERROR NAME"
    
    # Decrypt last name using the model method
        try:
            ret['last_name'] = instance.get_decrypted_last_name()
        except Exception as e:
            ret['last_name'] = "ERROR NAME"

        return ret

class ResetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.RegexField(
        regex=r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_])[A-Za-z\d@$!%*?&_]{8,}$',
        write_only=True,
        error_messages={'invalid': ('Password must be at least 8 characters long with at least one capital letter and symbol')})
    
    confirm_password = serializers.CharField(write_only=True, required=True)

class ClassroomSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    students = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = ['id', 'name', 'description', 'created_at', 'updated_at', 'teacher', 'teacher_name', 
                 'student_count', 'class_code', 'is_hidden', 'is_archived', 'students']
        read_only_fields = ['created_at', 'updated_at', 'teacher', 'class_code']

    def validate_name(self, value):
        # Check for duplicate names for the same teacher
        request = self.context.get('request')
        if request and request.user:
            if Classroom.objects.filter(teacher=request.user, name=value).exists():
                if self.instance and self.instance.name == value:  # Skip if it's an update with same name
                    return value
                raise serializers.ValidationError("You already have a classroom with this name")
        
        # Check name length and format
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Classroom name must be at least 3 characters long")
        if len(value) > 50:
            raise serializers.ValidationError("Classroom name cannot exceed 50 characters")
        
        return value

    def get_teacher_name(self, obj):
        return f"{obj.teacher.get_decrypted_first_name()} {obj.teacher.get_decrypted_last_name()}"

    def get_student_count(self, obj):
        return obj.students.count()

    def get_students(self, obj):
        request = self.context.get('request')
        return [
            {
                'id': student.id,
                'username': student.username,
                'name': f"{student.get_decrypted_first_name()} {student.get_decrypted_last_name()}",
                'avatar': request.build_absolute_uri(student.avatar.url) if student.avatar and student.avatar.name else None
            } for student in obj.students.all()
        ]

    def create(self, validated_data):
        # Get the teacher from the request context
        teacher = self.context['request'].user
        validated_data['teacher'] = teacher
        return super().create(validated_data)

class DrillSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    questions_input = serializers.ListField(write_only=True, required=False)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    custom_wordlist = serializers.PrimaryKeyRelatedField(queryset=WordList.objects.all(), required=False, allow_null=True)
    wordlist_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    wordlist_id = serializers.SerializerMethodField()

    class Meta:
        model = Drill
        fields = ['id', 'title', 'description', 'open_date', 'deadline', 'classroom', 'created_by', 'questions', 'questions_input', 'status', 'custom_wordlist', 'wordlist_name', 'wordlist_id', 'created_at']

    def get_questions(self, obj):
        """
        Serialize all questions for a drill by delegating to specific question type methods.
        Maintains the same JSON structure for frontend compatibility.
        """
        from .models import SmartSelectQuestion, BlankBustersQuestion, SentenceBuilderQuestion, PictureWordQuestion, MemoryGameQuestion
        
        result = []
        
        # Serialize each question type using dedicated methods
        result.extend(self._serialize_smart_select_questions(obj))
        result.extend(self._serialize_blank_busters_questions(obj))
        result.extend(self._serialize_sentence_builder_questions(obj))
        result.extend(self._serialize_picture_word_questions(obj))
        result.extend(self._serialize_memory_game_questions(obj))
        
        return result

    def _base_payload(self, question, question_type, drill_obj):
        """
        Create base payload with common fields for all question types.
        Includes wordlist media URL lookup for built-in drills.
        """
        payload = {
            'id': question.id,
            'text': getattr(question, 'text', None),
            'type': question_type,
            'word': getattr(question, 'word', None),
            'definition': getattr(question, 'definition', None),
        }
        
        # For built-in drills (no custom_wordlist), try to find media URLs
        if not drill_obj.custom_wordlist and question.word:
            media_urls = self._get_wordlist_media_urls(question.word)
            payload.update(media_urls)
        
        return payload

    def _get_wordlist_media_urls(self, word):
        """
        Look up media URLs for a word from built-in wordlists.
        Returns dict with 'image' and 'signVideo' keys if found.
        """
        import os
        import json
        from django.conf import settings
        
        wordlist_dir = os.path.join(settings.BASE_DIR, 'api', 'word-lists')
        if not os.path.exists(wordlist_dir):
            return {}
        
        for filename in os.listdir(wordlist_dir):
            if not filename.endswith('.json'):
                continue
                
            try:
                wordlist_file = os.path.join(wordlist_dir, filename)
                with open(wordlist_file, 'r', encoding='utf-8') as f:
                    wordlist_data = json.load(f)
                
                # Check if this word exists in this wordlist
                words = wordlist_data.get('words', [])
                matching_word = next(
                    (w for w in words if w.get('word', '').lower() == word.lower()), 
                    None
                )
                
                if matching_word:
                    # Found the wordlist! Return media URLs
                    media_urls = {}
                    if matching_word.get('image_url'):
                        media_urls['image'] = matching_word['image_url']
                    if matching_word.get('video_url'):
                        media_urls['signVideo'] = matching_word['video_url']
                    return media_urls
                    
            except Exception as e:
                print(f"Error reading wordlist {filename}: {e}")
                continue
        
        return {}

    def _serialize_choices(self, question):
        """
        Serialize choices for questions that use DrillChoice objects.
        Handles image and video URL building with request context.
        """
        request = self.context.get('request')
        choices = []
        
        for choice in question.choices_generic.all():
            choices.append({
                'id': choice.id,
                'text': choice.text,
                'is_correct': choice.is_correct,
                'image': self._get_media_url(choice.image, request),
                'video': self._get_media_url(choice.video, request),
            })
        
        return choices

    def _get_media_url(self, media_field, request):
        """
        Get absolute URL for media field, handling both request context and direct URLs.
        """
        if not media_field:
            return None
        
        if request:
            return request.build_absolute_uri(media_field.url)
        else:
            return media_field.url if hasattr(media_field, 'url') else None

    def _serialize_smart_select_questions(self, drill_obj):
        """
        Serialize SmartSelectQuestion (Multiple Choice) questions.
        """
        from .models import SmartSelectQuestion
        
        questions = []
        for question in SmartSelectQuestion.objects.filter(drill=drill_obj):
            payload = self._base_payload(question, 'M', drill_obj)
            payload['answer'] = question.answer
            payload['choices'] = self._serialize_choices(question)
            questions.append(payload)
        
        return questions

    def _serialize_blank_busters_questions(self, drill_obj):
        """
        Serialize BlankBustersQuestion (Fill-in-the-blank) questions.
        """
        from .models import BlankBustersQuestion
        
        questions = []
        for question in BlankBustersQuestion.objects.filter(drill=drill_obj):
            payload = self._base_payload(question, 'F', drill_obj)
            payload['letterChoices'] = question.letterChoices
            payload['answer'] = question.answer
            payload['pattern'] = question.pattern
            payload['hint'] = question.hint
            payload['choices'] = self._serialize_choices(question)
            questions.append(payload)
        
        return questions

    def _serialize_sentence_builder_questions(self, drill_obj):
        """
        Serialize SentenceBuilderQuestion (Drag & Drop) questions.
        """
        from .models import SentenceBuilderQuestion
        
        questions = []
        for question in SentenceBuilderQuestion.objects.filter(drill=drill_obj):
            payload = self._base_payload(question, 'D', drill_obj)
            payload['sentence'] = question.sentence
            payload['dragItems'] = question.dragItems
            payload['incorrectChoices'] = question.incorrectChoices
            questions.append(payload)
        
        return questions

    def _serialize_picture_word_questions(self, drill_obj):
        """
        Serialize PictureWordQuestion (Picture Selection) questions.
        """
        from .models import PictureWordQuestion
        
        questions = []
        for question in PictureWordQuestion.objects.filter(drill=drill_obj):
            payload = self._base_payload(question, 'P', drill_obj)
            payload['pictureWord'] = question.pictureWord
            payload['answer'] = question.answer
            questions.append(payload)
        
        return questions

    def _serialize_memory_game_questions(self, drill_obj):
        """
        Serialize MemoryGameQuestion (Memory Matching) questions.
        """
        from .models import MemoryGameQuestion
        
        questions = []
        for question in MemoryGameQuestion.objects.filter(drill=drill_obj):
            payload = self._base_payload(question, 'G', drill_obj)
            payload['memoryCards'] = question.memoryCards
            questions.append(payload)
        
        return questions

    def get_wordlist_id(self, obj):
        if obj.custom_wordlist:
            return obj.custom_wordlist.id
        elif obj.wordlist_name:
            return obj.wordlist_name
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        questions_data = validated_data.pop('questions_input', [])
        custom_wordlist = validated_data.pop('custom_wordlist', None)
        wordlist_name = validated_data.pop('wordlist_name', None)

        if isinstance(questions_data, str):
            import json
            questions_data = json.loads(questions_data)

        drill = Drill.objects.create(**validated_data)
        if custom_wordlist:
            drill.custom_wordlist = custom_wordlist
        if wordlist_name:
            drill.wordlist_name = wordlist_name
        drill.save()

        drill.create_with_questions(questions_data, request=request)
        return drill

    def update(self, instance, validated_data):
        request = self.context.get('request')
        
        # Update basic fields
        for attr, value in validated_data.items():
            if attr != 'questions_input':
                setattr(instance, attr, value)
        instance.save()
            
        # Process questions if provided
        questions_data = validated_data.get('questions_input')
        if questions_data is None:
            return instance
                
        if isinstance(questions_data, str):
            import json
            try:
                questions_data = json.loads(questions_data)
            except Exception:
                questions_data = []
            
        instance.update_with_questions(questions_data, request=request)
        return instance

class MemoryGameResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemoryGameResult
        fields = ['id', 'drill_result', 'question', 'attempts', 'matches', 'time_taken', 'score']
        read_only_fields = ['id', 'drill_result']

    def validate(self, data):
        # Validate that matches are valid pairs
        matches = data.get('matches', [])
        if not isinstance(matches, list):
            raise serializers.ValidationError("Matches must be a list")
        
        # Get the question's memory cards
        question = data['question']
        if question.type != 'G':
            raise serializers.ValidationError("Question must be a memory game type")
        
        cards = question.memoryCards
        valid_pairs = set()
        for card in cards:
            valid_pairs.add(frozenset([card['id'], card['pairId']]))
        
        # Validate each match
        for match in matches:
            if not isinstance(match, list) or len(match) != 2:
                raise serializers.ValidationError("Each match must be a pair of card IDs")
            if frozenset(match) not in valid_pairs:
                raise serializers.ValidationError(f"Invalid match: {match}")
        
        return data
    
class ClassroomPointsSerializer(serializers.Serializer):
    classroom_id = serializers.IntegerField()
    leaderboard = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of students with their total points, sorted by rank."
    )
    
class TransferRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    from_classroom_name = serializers.SerializerMethodField()
    to_classroom_name = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TransferRequest
        fields = ['id', 'student', 'student_name', 'from_classroom', 'from_classroom_name',
                 'to_classroom', 'to_classroom_name', 'requested_by', 'requested_by_name',
                 'status', 'created_at', 'updated_at', 'reason']
        read_only_fields = ['status', 'created_at', 'updated_at', 'requested_by']

    def get_student_name(self, obj):
        return f"{obj.student.get_decrypted_first_name()} {obj.student.get_decrypted_last_name()}"

    def get_from_classroom_name(self, obj):
        return obj.from_classroom.name

    def get_to_classroom_name(self, obj):
        return obj.to_classroom.name

    def get_requested_by_name(self, obj):
        return f"{obj.requested_by.get_decrypted_first_name()} {obj.requested_by.get_decrypted_last_name()}"

    def validate(self, data):
        # Get the student and classrooms
        student = data['student']
        from_classroom = data['from_classroom']
        to_classroom = data['to_classroom']

        # Check if student is in the from_classroom
        if not from_classroom.students.filter(id=student.id).exists():
            raise serializers.ValidationError("Student is not enrolled in the source classroom")

        # Check if student is already in the to_classroom
        if to_classroom.students.filter(id=student.id).exists():
            raise serializers.ValidationError("Student is already enrolled in the target classroom")

        # Check if from_classroom and to_classroom are different
        if from_classroom.id == to_classroom.id:
            raise serializers.ValidationError("Source and target classrooms must be different")

        # Check for existing pending transfer request
        if TransferRequest.objects.filter(
            student=student,
            from_classroom=from_classroom,
            to_classroom=to_classroom,
            status='pending'
        ).exists():
            raise serializers.ValidationError("A pending transfer request already exists for this student and classrooms")

        return data

class PromptSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=5000) # Adjust max_length as needed
    system_message = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    temperature = serializers.FloatField(required=False, default=0.7)
    max_tokens = serializers.IntegerField(required=False, default=500)

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'message', 'data', 'is_read', 'created_at']
        read_only_fields = ['created_at', 'type', 'message', 'data']

class VocabularySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vocabulary
        fields = ['id', 'word', 'definition', 'image_url', 'video_url']
        extra_kwargs = {
            'id': {'read_only': False, 'required': False} # <--- THIS IS KEY
        }

class WordListSerializer(serializers.ModelSerializer):
    words = VocabularySerializer(many=True)

    class Meta:
        model = WordList
        fields = ['id', 'name', 'description', 'words', 'created_by']

    def validate(self, data):
        word_texts = [word['word'].strip().lower() for word in data.get('words', [])]
        duplicates = [word for word, count in Counter(word_texts).items() if count > 1]
        if duplicates:
            raise serializers.ValidationError({
                'words': f'Duplicate words found (case-insensitive): {", ".join(duplicates)}'
            })
        return data
    
    def create(self, validated_data):
        created_by = self.context.get('request').user

        words_data = validated_data.pop('words')
        wordlist = WordList.objects.create(created_by=created_by, **validated_data)
        for word_data in words_data:
            Vocabulary.objects.create(list=wordlist, **word_data)
        return wordlist
    
    def update(self, instance, validated_data):
        # Update WordList fields
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()

        # Handle nested 'words'
        words_data = validated_data.get('words')
        if words_data is not None:  # Only update words if 'words' is provided in the payload
            existing_words = instance.words.all()
            existing_words_map = {word.id: word for word in existing_words} # Map existing words by their ID
            existing_word_texts_lower = {word.word.strip().lower() for word in existing_words}

            words_to_create = []
            words_to_update = []
            incoming_word_ids = set()

            # Keep track of words planned for creation to avoid duplicates within the new batch
            new_word_texts_lower_in_payload = set()

            for word_data in words_data:
                word_id = word_data.get('id') # <--- We explicitly look for 'id' here
                word_text_lower = word_data['word'].strip().lower() # Assuming 'word' is always present

                if word_id:
                    incoming_word_ids.add(word_id)
                    if word_id in existing_words_map: # <--- If 'id' is found in existing map, it's an update
                        words_to_update.append(word_data)
                    else:
                        raise serializers.ValidationError({
                            'words': f"Vocabulary item with ID '{word_id}' not found in this word list. "
                                     "Please provide an existing ID for updates or omit the ID for new creations."
                        })
                else:
                    # This is a new word to be created
                    # Check for duplicates against existing words in the list
                    if word_text_lower in existing_word_texts_lower:
                        raise serializers.ValidationError({
                            'words': f"Cannot add '{word_data['word']}' (case-insensitive) as it already exists in this word list."
                        })
                    
                    # Check for duplicates against other new words in the same payload
                    if word_text_lower in new_word_texts_lower_in_payload:
                        # This should theoretically be caught by the main validate method,
                        # but it's good to have a safeguard here too.
                        raise serializers.ValidationError({
                            'words': f"Duplicate new word '{word_data['word']}' (case-insensitive) found in the payload."
                        })

                    new_word_texts_lower_in_payload.add(word_text_lower)
                    words_to_create.append(word_data)

            # Create new words
            for word_data in words_to_create:
                Vocabulary.objects.create(list=instance, **word_data)

            # Update existing words
            for word_data in words_to_update:
                word_id = word_data['id']
                word_instance = existing_words_map[word_id] # Retrieve the existing instance
                for attr, value in word_data.items():
                    setattr(word_instance, attr, value) # Update its attributes
                word_instance.save() # Save the changes

            # Delete words not present in the payload (that were associated with the wordlist)
            words_to_delete = [
                word for word in existing_words if word.id not in incoming_word_ids
            ]
            for word in words_to_delete:
                word.delete()

        return instance

class QuestionResultSerializer(serializers.ModelSerializer):
    # You might want to include some question details here for easier frontend display
    question_id = serializers.SerializerMethodField()
    question_text = serializers.SerializerMethodField()
    question_type = serializers.SerializerMethodField()

    def get_question_id(self, obj):
        return obj.object_id if obj.question_generic else None
    
    def get_question_text(self, obj):
        return obj.question_generic.text if obj.question_generic else None
    
    def get_question_type(self, obj):
        return obj.question_generic.type if obj.question_generic else None

    class Meta:
        model = QuestionResult
        fields = ['id', 'question_id', 'question_text', 'question_type', 'submitted_answer', 'is_correct', 'time_taken', 'submitted_at', 'points_awarded']
        read_only_fields = ['id', 'question_id', 'question_text', 'question_type', 'submitted_at'] # These are set by the backend

class DrillResultSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    question_results = QuestionResultSerializer(many=True, read_only=True)

    class Meta:
        model = DrillResult
        fields = ['id', 'student', 'drill', 'run_number', 'start_time', 'completion_time', 'points', 'question_results']
        read_only_fields = ['drill', 'run_number', 'start_time', 'completion_time', 'points', 'question_results']

    def get_student(self, obj):
        first_name = obj.student.get_decrypted_first_name() or ''
        last_name = obj.student.get_decrypted_last_name() or ''
        request = self.context.get('request')
        avatar_url = None
        if obj.student.avatar:
            avatar_url = request.build_absolute_uri(obj.student.avatar.url) if request else obj.student.avatar.url
        return {
            'id': obj.student.id,
            'username': obj.student.username,
            'name': f'{first_name} {last_name}'.strip(),
            'avatar': avatar_url
        }

