from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Role

# Serializers that convert the Django Object to JSON, and vice versa

class UserSerializer(serializers.ModelSerializer):
  role = serializers.CharField(source="role.name", read_only=True)  # Include role in response
  role_input = serializers.ChoiceField(choices=Role.ROLE_CHOICES, write_only=True, required=True)

  class Meta:
    model = User
    fields = ["id", "username", "password", "first_name", "last_name", "email", "role", "role_input"]
    extra_kwargs = {"password": {"write_only": True}}     # exclude this data when it is requested

  def create(self, validated_data):
    role_name = validated_data.pop("role_input")                # Extract role from data
    user = User.objects.create_user(**validated_data)     # Create user object (password already hashed)
    Role.objects.create(user=user, name=role_name)        # Create role object (to know if user is student or teacher)
    return user