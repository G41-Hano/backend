from rest_framework import serializers
from .models import User, Role
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
    fields = ["id", "username", "password", "first_name", "last_name", "email", "role", "role_input", "first_name_encrypted", "last_name_encrypted"]
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