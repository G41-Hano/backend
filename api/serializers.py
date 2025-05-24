from rest_framework import serializers
from .models import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .utils.encryption import encrypt, decrypt
from collections import Counter

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


class UserSerializer(serializers.ModelSerializer):
  role = serializers.CharField(source="role.name", read_only=True)  # Include role in response
  role_input = serializers.ChoiceField(choices=Role.ROLE_CHOICES, write_only=True, required=True)

  class Meta:
    model = User
    fields = ["id", "username", "password", "first_name", "last_name", "email", "role", "role_input", "first_name_encrypted", "last_name_encrypted", "avatar"]
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

class DrillChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrillChoice
        fields = ['id', 'text', 'image', 'video', 'is_correct']

class DrillQuestionSerializer(serializers.ModelSerializer):
    choices = DrillChoiceSerializer(many=True, read_only=True)
    dragItems = serializers.JSONField(required=False)
    dropZones = serializers.JSONField(required=False)
    blankPosition = serializers.IntegerField(required=False, allow_null=True)
    memoryCards = serializers.JSONField(required=False)
    pictureWord = serializers.JSONField(required=False)
    story_title = serializers.CharField(required=False, allow_null=True)
    story_context = serializers.CharField(required=False, allow_null=True)
    sign_language_instructions = serializers.CharField(required=False, allow_null=True)
    answer = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = DrillQuestion
        fields = ['id', 'text', 'type', 'choices', 'dragItems', 'dropZones', 'blankPosition', 'memoryCards', 'pictureWord', 'story_title', 'story_context', 'sign_language_instructions', 'answer']

    def validate(self, data):
        if data.get('type') == 'G':  # Memory Game type
            if not data.get('memoryCards'):
                raise serializers.ValidationError("Memory cards are required for memory game questions")
            cards = data['memoryCards']
            if not isinstance(cards, list):
                raise serializers.ValidationError("Memory cards must be a list")
            if len(cards) < 2:
                raise serializers.ValidationError("At least 2 cards are required for a memory game")
            if len(cards) % 2 != 0:
                raise serializers.ValidationError("Number of cards must be even for matching pairs")
            # Validate each card has required fields
            for card in cards:
                if not isinstance(card, dict):
                    raise serializers.ValidationError("Each card must be an object")
                if 'id' not in card or 'content' not in card or 'pairId' not in card:
                    raise serializers.ValidationError("Each card must have id, content, and pairId fields")
        elif data.get('type') == 'P':  # Picture Word type
            if not data.get('pictureWord'):
                raise serializers.ValidationError("Pictures are required for Picture Word questions")
            pictures = data['pictureWord']
            if not isinstance(pictures, list):
                raise serializers.ValidationError("Pictures must be a list")
            if len(pictures) != 4:
                raise serializers.ValidationError("Exactly 4 pictures are required for Picture Word questions")
            # Validate each picture has required fields
            for pic in pictures:
                if not isinstance(pic, dict):
                    raise serializers.ValidationError("Each picture must be an object")
                if 'id' not in pic:
                    raise serializers.ValidationError("Each picture must have an id field")
        return data

class DrillSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    questions_input = serializers.ListField(write_only=True, required=False)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Drill
        fields = ['id', 'title', 'description', 'deadline', 'classroom', 'created_by', 'questions', 'questions_input', 'status']

    def get_questions(self, obj):
        return DrillQuestionSerializer(obj.questions.all(), many=True).data

    def create(self, validated_data):
        request = self.context.get('request')
        questions_data = validated_data.pop('questions_input', [])
        if isinstance(questions_data, str):
            import json
            questions_data = json.loads(questions_data)
        drill = Drill.objects.create(**validated_data)
        
        # Process each question
        for q_idx, question_data in enumerate(questions_data):
            choices_data = question_data.pop('choices', [])
            # Store the answer field
            answer = question_data.get('answer')
            print(f"Creating question with answer: {answer}")  # Debug log
            
            # Create the question with the answer field
            question = DrillQuestion.objects.create(drill=drill, **question_data)
            
            # Handle choices for multiple choice and fill in the blank
            for c_idx, choice_data in enumerate(choices_data):
                media_key = choice_data.pop('media', None)
                image = None
                video = None
                if media_key and isinstance(media_key, str) and request and media_key in request.FILES:
                    file = request.FILES[media_key]
                    if file.content_type.startswith('image/'):
                        image = file
                    elif file.content_type.startswith('video/'):
                        video = file
                DrillChoice.objects.create(
                    question=question,
                    text=choice_data.get('text', ''),
                    is_correct=str(choice_data.get('is_correct', False)).lower() == 'true',
                    image=image,
                    video=video,
                )
            
            # Handle memory game cards
            if question_data.get('type') == 'G':
                memory_cards = question_data.get('memoryCards', [])
                for c_idx, card_data in enumerate(memory_cards):
                    media_key = card_data.get('media')
                    if media_key and isinstance(media_key, str) and request and media_key in request.FILES:
                        file = request.FILES[media_key]
                        if file.content_type.startswith('image/'):
                            try:
                                from django.core.files.storage import default_storage
                                file_path = f'drill_choices/images/{file.name}'
                                saved_path = default_storage.save(file_path, file)
                                card_data['media'] = {
                                    'url': request.build_absolute_uri(default_storage.url(saved_path)),
                                    'type': file.content_type
                                }
                            except Exception as e:
                                print(f"Error saving memory game image: {e}")
                                card_data['media'] = None
                        elif file.content_type.startswith('video/'):
                            try:
                                from django.core.files.storage import default_storage
                                file_path = f'drill_choices/videos/{file.name}'
                                saved_path = default_storage.save(file_path, file)
                                card_data['media'] = {
                                    'url': request.build_absolute_uri(default_storage.url(saved_path)),
                                    'type': file.content_type
                                }
                            except Exception as e:
                                print(f"Error saving memory game video: {e}")
                                card_data['media'] = None
                question.memoryCards = memory_cards
                question.save()

            # Handle picture word images
            if question_data.get('type') == 'P':
                pictures = question_data.get('pictureWord', [])
                updated_pictures = [] # Create a new list to store updated picture data
                for p_idx, pic_data in enumerate(pictures):
                    media_value = pic_data.get('media')
                    processed_media = None

                    if media_value and isinstance(media_value, str) and request and media_value in request.FILES:
                        # This is a new file upload referenced by a key from frontend
                        file = request.FILES[media_value]
                        # Ensure it's an image before saving
                        if file.content_type.startswith('image/'):
                            try:
                                from django.core.files.storage import default_storage
                                # Define the target path within your media storage
                                file_path = f'drill_choices/images/{file.name}'

                                # Save the file using the default storage
                                saved_path = default_storage.save(file_path, file)

                                # Create the media data object with the saved file's URL
                                processed_media = {
                                    'url': request.build_absolute_uri(default_storage.url(saved_path)),
                                    'type': file.content_type
                                }
                                print(f"Backend: Saved new picture word image to: {saved_path}") # Debugging

                            except Exception as e:
                                print(f"Backend: Error saving picture word file {file.name}: {e}") # Debugging
                                # If saving fails, do not add this media
                                processed_media = None # Explicitly set to None
                        else:
                             # Handle non-image files if necessary, or skip
                             print(f"Backend: Skipping non-image file for picture word: {file.name}") # Debugging
                             processed_media = None

                    elif media_value and isinstance(media_value, dict) and 'url' in media_value:
                        # This is existing media data with a URL, keep it as is
                        processed_media = media_value
                        print(f"Backend: Keeping existing picture word image URL: {media_value['url']}") # Debugging

                    # Add the picture data with the processed media (or original if no media was provided or processed)
                    updated_pic_data = {**pic_data}
                    if processed_media is not None:
                        updated_pic_data['media'] = processed_media
                    elif 'media' in updated_pic_data and processed_media is None and isinstance(media_value, str) and media_value in request.FILES:
                         # If a file was attempted but failed to save (processed_media is None), remove the media key from the data being saved
                         del updated_pic_data['media']
                    # If media_value was not provided at all, the original pic_data without media is fine

                    updated_pictures.append(updated_pic_data)

                # Assign the list of updated picture data back to the question
                question.pictureWord = updated_pictures
                question.save()
        return drill

    def update(self, instance, validated_data):
        try:
            request = self.context.get('request')
            
            # Handle the basic drill fields first
            for attr, value in validated_data.items():
                if attr != 'questions_input':
                    setattr(instance, attr, value)
            instance.save()
            
            # Process questions if provided
            questions_data = validated_data.get('questions_input')
            if questions_data is None:
                return instance
                
            if not isinstance(questions_data, list):
                if isinstance(questions_data, str):
                    try:
                        import json
                        questions_data = json.loads(questions_data)
                        if not isinstance(questions_data, list):
                            questions_data = []
                    except:
                        questions_data = []
                else:
                    questions_data = []
            
            existing_questions = {str(q.id): q for q in instance.questions.all()}
            questions_to_keep = []
            
            # Process each question in the input
            for question_data in questions_data:
                # Handle string conversion if needed
                if isinstance(question_data, str):
                    try:
                        import json
                        question_data = json.loads(question_data)
                    except:
                        continue
                
                if not isinstance(question_data, dict):
                    continue
                
                # Safe copy to avoid modifying the original
                question_dict = question_data.copy()
                
                # Extract question ID if present
                question_id = None
                if 'id' in question_dict:
                    try:
                        question_id = str(question_dict.pop('id'))
                    except (TypeError, ValueError):
                        question_id = None
                
                choices_data = []
                if 'choices' in question_dict:
                    choices = question_dict.pop('choices')
                    if isinstance(choices, list):
                        choices_data = choices
                
                # Remove fields that shouldn't be part of the model
                for field in ['created_at', 'updated_at', 'answer']:
                    if field in question_dict:
                        question_dict.pop(field)
                
                # Handle existing question update
                question = None
                if question_id and question_id in existing_questions:
                    question = existing_questions[question_id]
                    # Update fields
                    for attr, value in question_dict.items():
                        setattr(question, attr, value)
                    question.save()
                    questions_to_keep.append(question.id)
                    
                    # Delete existing choices for this question
                    question.choices.all().delete()
                else:
                    # Create new question
                    try:
                        question = DrillQuestion.objects.create(drill=instance, **question_dict)
                        questions_to_keep.append(question.id)
                    except Exception as e:
                        print(f"Error creating question: {e}")
                        continue
                
                # Add choices if we have a valid question
                if question:
                    for choice_data in choices_data:
                        try:
                            if isinstance(choice_data, str):
                                import json
                                choice_data = json.loads(choice_data)
                            
                            if not isinstance(choice_data, dict):
                                continue
                                
                            # Handle media
                            media_key = None
                            if 'media' in choice_data:
                                media_key = choice_data.pop('media')
                            
                            image = None
                            video = None
                            
                            # Handle new file uploads
                            if media_key and isinstance(media_key, str) and request and media_key in request.FILES:
                                file = request.FILES[media_key]
                                if file.content_type.startswith('image/'):
                                    image = file
                                elif file.content_type.startswith('video/'):
                                    video = file
                            # Handle existing media
                            elif media_key and isinstance(media_key, dict):
                                # Check if the media has a URL
                                if 'url' in media_key:
                                    url = media_key['url']
                                    # Extract filename from URL
                                    import os
                                    from urllib.parse import urlparse
                                    
                                    # Try to determine if it's an image or video from the URL or type
                                    is_image = False
                                    is_video = False
                                    
                                    # Check if type is provided
                                    media_type = media_key.get('type', '')
                                    if isinstance(media_type, str):
                                        is_image = media_type.startswith('image/')
                                        is_video = media_type.startswith('video/')
                                    
                                    # If no type or couldn't determine, try from URL extension
                                    if not (is_image or is_video):
                                        parsed_url = urlparse(url)
                                        path = parsed_url.path
                                        ext = os.path.splitext(path)[1].lower()
                                        is_image = ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
                                        is_video = ext in ['.mp4', '.webm', '.mov', '.avi']
                                    
                                    # extract the relative path from the URL
                                    # Find the media path in the URL
                                    if '/media/' in url:
                                        relative_path = url.split('/media/')[1]
                                        
                                        if is_image:
                                            from django.core.files.storage import default_storage
                                            if default_storage.exists(f"drill_choices/images/{os.path.basename(relative_path)}"):
                                                image = f"drill_choices/images/{os.path.basename(relative_path)}"
                                            else:
                                                image = relative_path
                                        elif is_video:
                                            from django.core.files.storage import default_storage
                                            if default_storage.exists(f"drill_choices/videos/{os.path.basename(relative_path)}"):
                                                video = f"drill_choices/videos/{os.path.basename(relative_path)}"
                                            else:
                                                video = relative_path
                            
                            is_correct = False
                            if 'is_correct' in choice_data:
                                is_correct_val = choice_data.get('is_correct')
                                if isinstance(is_correct_val, bool):
                                    is_correct = is_correct_val
                                elif isinstance(is_correct_val, str):
                                    is_correct = is_correct_val.lower() == 'true'
                            
                            # Create choice
                            try:
                                # Clean choice data
                                choice_dict = {
                                    'question': question,
                                    'text': choice_data.get('text', ''),
                                    'is_correct': is_correct,
                                }
                                
                                if image:
                                    choice_dict['image'] = image
                                if video:
                                    choice_dict['video'] = video
                                
                                # Debug output
                                print(f"Creating choice for question {question.id}: {choice_dict}")
                                
                                choice = DrillChoice.objects.create(**choice_dict)
                                print(f"Successfully created choice {choice.id}")
                            except Exception as e:
                                print(f"Error creating choice: {str(e)}")
                                import traceback
                                print(traceback.format_exc())
                                continue
                        except Exception as e:
                            print(f"Error processing choice: {e}")
                            continue
            
            # Delete questions not in the update list
            if questions_data:  # Only delete if we received questions data
                questions_to_delete = set(existing_questions.keys()) - set(str(q_id) for q_id in questions_to_keep)
                for q_id in questions_to_delete:
                    try:
                        existing_questions[q_id].delete()
                    except Exception as e:
                        print(f"Error deleting question {q_id}: {e}")
            
            return instance
        except Exception as e:
            print(f"Error in drill update: {e}")
            raise

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
        read_only_fields = ['status', 'created_at', 'updated_at']

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

        return data

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'message', 'data', 'is_read', 'created_at']
        read_only_fields = ['created_at']


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

# Add serializer for QuestionResult
class QuestionResultSerializer(serializers.ModelSerializer):
    # You might want to include some question details here for easier frontend display
    question_id = serializers.PrimaryKeyRelatedField(source='question.id', read_only=True)
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.type', read_only=True)

    class Meta:
        model = QuestionResult
        fields = ['id', 'question_id', 'question_text', 'question_type', 'submitted_answer', 'is_correct', 'time_taken', 'submitted_at', 'points_awarded']
        read_only_fields = ['id', 'question_id', 'question_text', 'question_type', 'submitted_at'] # These are set by the backend

# Add serializer for DrillResult
class DrillResultSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    question_results = QuestionResultSerializer(many=True, read_only=True) # Nested serializer for question results
    # We cannot include nested question-specific results easily with current models
    # For Memory Game results, we could potentially add a nested serializer here
    # memory_game_results = MemoryGameResultSerializer(many=True, read_only=True) # This would require a reverse relationship access

    class Meta:
        model = DrillResult
        fields = ['id', 'student', 'drill', 'run_number', 'start_time', 'completion_time', 'points', 'question_results']
        read_only_fields = ['drill', 'run_number', 'start_time', 'completion_time', 'points', 'question_results'] # These are set by the system

    def get_student(self, obj):
        first_name = obj.student.get_decrypted_first_name() or ''
        last_name = obj.student.get_decrypted_last_name() or ''
        return {
            'id': obj.student.id,
            'username': obj.student.username,
            'name': f'{first_name} {last_name}'.strip(),
        }

