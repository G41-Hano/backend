from django.shortcuts import render
from .models import User, PasswordReset, Classroom
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, CustomTokenSerializer, ResetPasswordRequestSerializer, ResetPasswordSerializer, ClassroomSerializer
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
  permission_classes = [IsAuthenticated]

  def get_queryset(self):
    queryset = User.objects.all()
    role = self.request.query_params.get('role', None)
    if role:
        queryset = queryset.filter(role__name=role)
    return queryset

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

class ClassroomListView(generics.ListCreateAPIView): # creates the classroom and displays classrooms of the teacher
    serializer_class = ClassroomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role.name == 'teacher':
            return Classroom.objects.filter(teacher=user).order_by('order', '-created_at')
        else:
            return Classroom.objects.filter(students=user).order_by('order', '-created_at')

    def create(self, request, *args, **kwargs):
        if request.user.role.name != 'teacher':
            return Response(
                {"error": "Only teachers can create classrooms"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Set the order to be the last in the list
        last_classroom = Classroom.objects.filter(teacher=request.user).order_by('-order').first()
        next_order = (last_classroom.order + 1) if last_classroom else 0
        request.data['order'] = next_order
        
        return super().create(request, *args, **kwargs)

class ClassroomDetailView(generics.RetrieveUpdateDestroyAPIView): # updates and deletes a classroom
    serializer_class = ClassroomSerializer
    permission_classes = [IsAuthenticated]
    queryset = Classroom.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.role.name == 'teacher':
            return Classroom.objects.filter(teacher=user)
        else:
            return Classroom.objects.filter(students=user)

    def update(self, request, *args, **kwargs):
        # Allow students to update only student_color, is_hidden, and order
        if request.user.role.name == 'student':
            if set(request.data.keys()) - {'student_color', 'is_hidden', 'order'}:
                return Response(
                    {"error": "Students can only update their color preference, visibility, and order"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            # Verify student is enrolled in this classroom
            classroom = self.get_object()
            if request.user not in classroom.students.all():
                return Response(
                    {"error": "You are not enrolled in this classroom"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            return super().update(request, *args, **kwargs)
        
        # For teachers, allow all updates
        if request.user.role.name != 'teacher':
            return Response(
                {"error": "Only teachers can update classrooms"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role.name != 'teacher':
            return Response(
                {"error": "Only teachers can delete classrooms"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

class ClassroomStudentsView(APIView): # enroll and delete students in a classroom
    permission_classes = [IsAuthenticated]
    MAX_STUDENTS = 50  # Maximum students per classroom

    def get(self, request, pk):
        """
        Get a list of students enrolled in the classroom.
        """
        try:
            classroom = Classroom.objects.get(pk=pk)
            if request.user != classroom.teacher and request.user not in classroom.students.all():
                return Response(
                    {"error": "You don't have permission to view this classroom's students"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            students = classroom.students.all()
            return Response({
                'count': students.count(),
                'students': [
                    {
                        'id': student.id,
                        'username': student.username,
                        'name': f"{student.get_decrypted_first_name()} {student.get_decrypted_last_name()}",
                        'avatar': request.build_absolute_uri(student.avatar.url) if student.avatar else None
                    } for student in students
                ]
            })
        except Classroom.DoesNotExist:
            return Response(
                {'error': 'Classroom not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request, pk):
        """
        Add students to the classroom.
        
        Expects a JSON body with:
        {
            "student_ids": [1, 2, 3]  // List of student user IDs to enroll
        }
        
        Rules:
        - Only teachers can add students
        - Maximum 50 students per classroom
        - Cannot add already enrolled students
        - Can only add users with student role
        """
        # Check if user is a teacher
        if request.user.role.name != 'teacher':
            return Response(
                {"error": "Only teachers can add students"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            classroom = Classroom.objects.get(pk=pk, teacher=request.user)
            student_ids = request.data.get('student_ids', [])
            
            # Check if student_ids is empty
            if not student_ids:
                return Response(
                    {"error": "No student IDs provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check student limit
            current_students = classroom.students.count()
            if current_students + len(student_ids) > self.MAX_STUDENTS:
                return Response(
                    {
                        "error": f"Cannot add students. Maximum limit is {self.MAX_STUDENTS}. "
                        f"Current count: {current_students}"
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if any students are already enrolled
            already_enrolled = classroom.students.filter(id__in=student_ids).values_list('id', flat=True)
            if already_enrolled:
                return Response(
                    {
                        "error": "Some students are already enrolled",
                        "already_enrolled_ids": list(already_enrolled)
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verify all users exist and are students
            students = User.objects.filter(id__in=student_ids, role__name='student')
            if len(students) != len(student_ids):
                invalid_ids = set(student_ids) - set(students.values_list('id', flat=True))
                return Response(
                    {
                        "error": "Some user IDs are invalid or not students",
                        "invalid_ids": list(invalid_ids)
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            classroom.students.add(*students)
            return Response(
                {
                    'success': 'Students added successfully',
                    'added_count': len(students),
                    'total_students': classroom.students.count()
                },
                status=status.HTTP_200_OK
            )
        except Classroom.DoesNotExist:
            return Response(
                {'error': 'Classroom not found or you are not the teacher'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, pk):
        """
        Remove students from the classroom.
        
        Expects a JSON body with:
        {
            "student_ids": [1, 2, 3]  // List of student user IDs to remove
        }
        
        Rules:
        - Only teachers can remove students
        - Can only remove enrolled students
        """
        # Check if user is a teacher
        if request.user.role.name != 'teacher':
            return Response(
                {"error": "Only teachers can remove students"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            classroom = Classroom.objects.get(pk=pk, teacher=request.user)
            student_ids = request.data.get('student_ids', [])
            
            # Check if student_ids is empty
            if not student_ids:
                return Response(
                    {"error": "No student IDs provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verify students are in the classroom
            enrolled_students = classroom.students.filter(id__in=student_ids)
            if len(enrolled_students) != len(student_ids):
                not_enrolled = set(student_ids) - set(enrolled_students.values_list('id', flat=True))
                return Response(
                    {
                        "error": "Some students are not enrolled in this classroom",
                        "not_enrolled_ids": list(not_enrolled)
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            classroom.students.remove(*enrolled_students)
            return Response(
                {
                    'success': 'Students removed successfully',
                    'removed_count': len(enrolled_students),
                    'total_students': classroom.students.count()
                },
                status=status.HTTP_200_OK
            )
        except Classroom.DoesNotExist:
            return Response(
                {'error': 'Classroom not found or you are not the teacher'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class JoinClassroomView(APIView):
    """
    View for students to join a classroom using a class code.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Join a classroom using a class code.
        
        Expects a JSON body with:
        {
            "class_code": "ABC123"  // The class code to join
        }
        
        Rules:
        - Only students can join classrooms
        - Class code must be valid
        - Student must not be already enrolled
        - Classroom must not be at maximum capacity
        """
        # Check if user is a student
        if request.user.role.name != 'student':
            return Response(
                {"error": "Only students can join classrooms"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        class_code = request.data.get('class_code')
        if not class_code:
            return Response(
                {"error": "Class code is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            classroom = Classroom.objects.get(class_code=class_code)
            
            # Check if student is already enrolled
            if request.user in classroom.students.all():
                return Response(
                    {"error": "You are already enrolled in this classroom"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if classroom is at maximum capacity
            if classroom.students.count() >= 50:  # Using the same limit as ClassroomStudentsView
                return Response(
                    {"error": "This classroom is at maximum capacity"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Add student to classroom
            classroom.students.add(request.user)
            
            return Response(
                {
                    'success': 'Successfully joined the classroom',
                    'classroom_id': classroom.id,
                    'classroom_name': classroom.name
                },
                status=status.HTTP_200_OK
            )
        except Classroom.DoesNotExist:
            return Response(
                {"error": "Invalid class code"}, 
                status=status.HTTP_404_NOT_FOUND
            )