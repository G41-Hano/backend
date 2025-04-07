from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, CustomTokenSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView

# Create your views here.

class CustomTokenView(TokenObtainPairView):
  serializer_class = CustomTokenSerializer

class CreateUserView(generics.CreateAPIView):
  queryset = User.objects.all()
  serializer_class = UserSerializer
  permission_classes = [AllowAny]

class UserListView(generics.ListAPIView):
  queryset = User.objects.all()
  serializer_class = UserSerializer
  permission_classes = [AllowAny]

# class UserView(APIView):
#   permission_classes = [IsAuthenticated]
#   def get(self, request):
#     return Response(UserSerializer(request.user).data)  # <- The user from the token