from rest_framework import serializers
from .models import User, Role, Classroom
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
                 'student_count', 'class_code', 'color', 'student_color', 'is_hidden', 'students', 'order']
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