from rest_framework import serializers
from .models import User, Role, Classroom, Drill, DrillQuestion, DrillChoice
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .utils.encryption import encrypt, decrypt

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
                 'student_count', 'class_code', 'color', 'student_color', 'is_hidden', 'is_archived', 'students', 'order']
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

    class Meta:
        model = DrillQuestion
        fields = ['id', 'text', 'type', 'choices', 'dragItems', 'dropZones', 'blankPosition']

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
        for q_idx, question_data in enumerate(questions_data):
            choices_data = question_data.pop('choices')
            question_data.pop('answer', None)
            question = DrillQuestion.objects.create(drill=drill, **question_data)
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