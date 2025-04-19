from django.shortcuts import render
from .models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import PasswordReset
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, CustomTokenSerializer, ResetPasswordRequestSerializer, ResetPasswordSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework import status
import os
import secrets
from django.conf import settings

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

class CheckUsernameView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        if not username:
            return Response({'error': 'Username is required'}, status=400)
            
        exists = User.objects.filter(username=username).exists()
        return Response({
            'exists': exists,
            'message': 'Username already exists' if exists else 'Username is available'
        })

# class UserView(APIView):
#   permission_classes = [IsAuthenticated]
#   def get(self, request):
#     return Response(UserSerializer(request.user).data)  # <- The user from the token

class RequestPasswordReset(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordRequestSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
          email = request.data['email']
          user = User.objects.filter(email__iexact=email).first()

          if user:
              token = secrets.token_urlsafe(48)
              reset = PasswordReset(email=email, token=token)
              reset.save()
              
              reset_url = f"{settings.PASSWORD_RESET_BASE_URL}/{token}"
              
              # Render the HTML email template with context
              subject = "Password Reset Request"
              html_message = render_to_string('emails/password_reset_email.html', {'reset_url': reset_url})
              plain_message = strip_tags(html_message)  # Converts HTML to plain text
              from_email = settings.DEFAULT_FROM_EMAIL
              
              # Send the email
              send_mail(
                 subject,  # Email subject
                 plain_message,  # Plain text message
                 from_email,  # From email
                 [email],  # Recipient email
                 html_message=html_message  # HTML message
            )

              return Response({'success': 'We have sent you a link to reset your password'}, status=status.HTTP_200_OK)
          else:
              return Response({"error": "User with credentials not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class ResetPassword(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = []

    def post(self, request, token):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        new_password = data['new_password']
        confirm_password = data['confirm_password']
        
        if new_password != confirm_password:
            return Response({"error": "Passwords do not match"}, status=400)
        
        reset_obj = PasswordReset.objects.filter(token=token).first()
        
        if not reset_obj or reset_obj.is_expired():
            if reset_obj:
              reset_obj.delete()
            return Response({'error':'Invalid or expired token'}, status=400)
        
        user = User.objects.filter(email=reset_obj.email).first()
        
        if user:
            user.set_password(request.data['new_password'])
            user.save()
            
            reset_obj.delete()
            
            return Response({'success':'Password updated successfully'})
        else: 
            return Response({'error':'No user found'}, status=404)