from django.shortcuts import render
from .models import User, Role, PasswordReset, Classroom, Drill, DrillQuestion, DrillResult, MemoryGameResult, TransferRequest, Notification, QuestionResult, Badge
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import generics, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, CustomTokenSerializer, ResetPasswordRequestSerializer, ResetPasswordSerializer, ClassroomSerializer, DrillSerializer, TransferRequestSerializer, NotificationSerializer, DrillResultSerializer, BadgeSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework import status
import secrets
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.storage import default_storage
import pandas as pd
from django.contrib.auth.hashers import make_password
from rest_framework.decorators import api_view, permission_classes, action
from api.utils.encryption import encrypt, decrypt  # Import the decrypt function
from cryptography.fernet import InvalidToken  # Import the InvalidToken exception
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Avg, Max
import os
import math
import logging

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
            user.first_name = decrypt(user.first_name_encrypted)
            user.last_name = decrypt(user.last_name_encrypted)
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
            return Classroom.objects.filter(teacher=user).order_by('-created_at')
        else:
            return Classroom.objects.filter(students=user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        if request.user.role.name != 'teacher':
            return Response(
                {"error": "Only teachers can create classrooms"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
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
        # Allow students to update only is_hidden
        if request.user.role.name == 'student':
            if set(request.data.keys()) - {'is_hidden'}:
                return Response(
                    {"error": "Students can only update visibility"}, 
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
        Get a list of students enrolled in the classroom or the leaderboard.
        """
        try:
            classroom = Classroom.objects.get(pk=pk)
            if request.user != classroom.teacher and request.user not in classroom.students.all():
                return Response(
                    {"error": "You don't have permission to view this classroom's students"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if this is a leaderboard request
            if request.path.endswith('/leaderboard/'):
                # Get all students in the classroom
                students = classroom.students.all()
                
                leaderboard_data = []
                for student in students:
                    # Get all drill results for this student in this classroom
                    drill_results = DrillResult.objects.filter(
                        student=student,
                        drill__classroom=classroom
                    ).select_related('drill')
                    
                    # Calculate total points using the best score for each drill
                    classroom_points = 0
                    drill_scores = {}  # Track best scores per drill
                    
                    for result in drill_results:
                        drill_id = result.drill.id
                        if drill_id not in drill_scores or result.points > drill_scores[drill_id]:
                            drill_scores[drill_id] = result.points
                    
                    # Sum up the best scores
                    classroom_points = sum(drill_scores.values())
                    
                    leaderboard_data.append({
                        'id': student.id,
                        'first_name': student.get_decrypted_first_name(),
                        'last_name': student.get_decrypted_last_name(),
                        'avatar': request.build_absolute_uri(student.avatar.url) if student.avatar else None,
                        'points': classroom_points,
                        'drill_scores': drill_scores  # Include drill scores for detailed view
                    })
                
                # Sort by points in descending order
                leaderboard_data.sort(key=lambda x: x['points'], reverse=True)
                return Response(leaderboard_data)
            
            # Regular student list request
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

    @action(detail=True, methods=['get'])
    def leaderboard(self, request, pk):
        """
        Get the leaderboard for a classroom showing student rankings based on points.
        """
        try:
            classroom = Classroom.objects.get(pk=pk)
            if request.user != classroom.teacher and request.user not in classroom.students.all():
                return Response(
                    {"error": "You don't have permission to view this classroom's leaderboard"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get all students in the classroom
            students = classroom.students.all()
            
            leaderboard_data = []
            for student in students:
                # Get all drill results for this student in this classroom
                drill_results = DrillResult.objects.filter(
                    student=student,
                    drill__classroom=classroom
                ).select_related('drill')
                
                # Calculate total points using the best score for each drill
                classroom_points = 0
                drill_scores = {}  # Track best scores per drill
                
                for result in drill_results:
                    drill_id = result.drill.id
                    if drill_id not in drill_scores or result.points > drill_scores[drill_id]:
                        drill_scores[drill_id] = result.points
                
                # Sum up the best scores
                classroom_points = sum(drill_scores.values())
                
                leaderboard_data.append({
                    'id': student.id,
                    'first_name': student.get_decrypted_first_name(),
                    'last_name': student.get_decrypted_last_name(),
                    'avatar': request.build_absolute_uri(student.avatar.url) if student.avatar else None,
                    'points': classroom_points,
                    'drill_scores': drill_scores  # Include drill scores for detailed view
                })
            
            # Sort by points in descending order
            leaderboard_data.sort(key=lambda x: x['points'], reverse=True)
            return Response(leaderboard_data)
            
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

            # Create notifications for each added student
            for student in students:
                Notification.objects.create(
                    recipient=student,
                    type='student_added',
                    message=f"You have been added to the classroom {classroom.name} by {request.user.get_decrypted_first_name()} {request.user.get_decrypted_last_name()}",
                    data={
                        'classroom_id': classroom.id,
                        'classroom_name': classroom.name,
                        'teacher_id': request.user.id,
                        'teacher_name': f"{request.user.get_decrypted_first_name()} {request.user.get_decrypted_last_name()}"
                    }
                )

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

            # Create notifications for each removed student
            for student in enrolled_students:
                Notification.objects.create(
                    recipient=student,
                    type='student_removed',
                    message=f"You have been removed from the classroom {classroom.name} by {request.user.get_decrypted_first_name()} {request.user.get_decrypted_last_name()}",
                    data={
                        'classroom_id': classroom.id,
                        'classroom_name': classroom.name,
                        'teacher_id': request.user.id,
                        'teacher_name': f"{request.user.get_decrypted_first_name()} {request.user.get_decrypted_last_name()}"
                    }
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

class DrillListCreateView(generics.ListCreateAPIView):
    serializer_class = DrillSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        classroom_id = self.request.query_params.get('classroom')
        
        if user.role.name == 'teacher':
            qs = Drill.objects.filter(created_by=user)
        else:
            # Students can access drills from their classrooms
            qs = Drill.objects.filter(classroom__students=user)
            
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
            
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        questions_input = data.get('questions_input') or data.get('questions')
        if isinstance(questions_input, str):
            import json
            questions_input = json.loads(questions_input)
        serializer_data = {
            'title': data.get('title'),
            'description': data.get('description'),
            'deadline': data.get('deadline'),
            'classroom': data.get('classroom'),
            'status': data.get('status'),
            'questions_input': questions_input,
            'custom_wordlist': data.get('custom_wordlist'),
        }
        serializer = self.get_serializer(data=serializer_data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class DrillRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Drill.objects.all()
    serializer_class = DrillSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        # Filter by user to ensure they can only access their own drills
        user = self.request.user
        if user.role.name == 'teacher':
            return Drill.objects.filter(created_by=user)
        else:
            # Students can access drills from their classrooms
            return Drill.objects.filter(classroom__students=user)

    def perform_destroy(self, instance):
        # Only allow the creator (teacher) to delete
        user = self.request.user
        if user.role.name != 'teacher' or instance.created_by != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only the creator teacher can delete this drill.')
        return super().perform_destroy(instance)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
            # Create a mutable copy of the data
            data = {}
            
            # Handle MultiValueDict from request.data
            if hasattr(request.data, 'dict'):
                data = request.data.dict()
            else:
                # Copy each item from request.data
                for key in request.data:
                    data[key] = request.data[key]
            
            # Process questions data if present
            questions_input = request.data.get('questions_input') or request.data.get('questions')
            
            if questions_input:
                # Handle string JSON input
                if isinstance(questions_input, str):
                    try:
                        import json
                        data['questions_input'] = json.loads(questions_input)
                    except json.JSONDecodeError as e:
                        return Response(
                            {"error": f"Invalid JSON in questions_input field: {str(e)}"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    data['questions_input'] = questions_input
            
            # Create and validate serializer
            serializer = self.get_serializer(
                instance,
                data=data,
                context={'request': request},
                partial=partial
            )
            
            try:
                serializer.is_valid(raise_exception=True)
            except Exception as e:
                return Response(
                    {"error": f"Validation error: {str(e)}", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Perform the update
            try:
                self.perform_update(serializer)
            except Exception as e:
                import traceback
                return Response(
                    {
                        "error": f"Error updating drill: {str(e)}",
                        "traceback": traceback.format_exc()
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if getattr(instance, '_prefetched_objects_cache', None):
                # If 'prefetch_related' has been applied to a queryset, we need to
                # forcibly invalidate the prefetch cache on the instance.
                instance._prefetched_objects_cache = {}
                
            return Response(serializer.data)
            
        except Exception as e:
            import traceback
            return Response(
                {
                    "error": f"Unexpected error: {str(e)}",
                    "traceback": traceback.format_exc()
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class MemoryGameSubmissionView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, drill_id, question_id):
        try:
            # Get the drill and question
            drill = Drill.objects.get(id=drill_id)
            question = DrillQuestion.objects.get(id=question_id, drill=drill)
            
            if question.type != 'G':
                return Response(
                    {"error": "Question is not a memory game type"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get or create drill result
            drill_result, created = DrillResult.objects.get_or_create(
                student=request.user,
                drill=drill,
                defaults={
                    'run_number': 1,
                    'completion_time': timezone.now(),
                    'points': 0
                }
            )
            
            if not created:
                drill_result.run_number += 1
                drill_result.completion_time = timezone.now()
                drill_result.save()
            
            # Calculate score based on attempts and time
            attempts = request.data.get('attempts', 0)
            time_taken = request.data.get('time_taken', 0)
            matches = request.data.get('matches', [])
            
            # Score calculation
            base_score = 100
            attempt_penalty = attempts * 5  # 5 points penalty per attempt
            time_penalty = time_taken * 0.1  # 0.1 points penalty per second
            score = max(0, base_score - attempt_penalty - time_penalty)
            
            # Create memory game result
            memory_result = MemoryGameResult.objects.create(
                drill_result=drill_result,
                question=question,
                attempts=attempts,
                matches=matches,
                time_taken=time_taken,
                score=score
            )
            
            # Update drill result points
          #  drill_result.points = score
            total_points_for_run = drill_result.question_results.aggregate(total=models.Sum('points_awarded'))['total'] or 0
            drill_result.points = total_points_for_run
            drill_result.save()
            
            # Update user's total points and check for badges
            request.user.update_points_and_badges(total_points_for_run)
            
            return Response({
                'success': True,
                'score': score,
                'attempts': attempts,
                'time_taken': time_taken
            })
            
        except Drill.DoesNotExist:
            return Response(
                {"error": "Drill not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DrillQuestion.DoesNotExist:
            return Response(
                {"error": "Question not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

# Profile View
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get the current user's profile information"""
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.get_decrypted_first_name(),
            'last_name': user.get_decrypted_last_name(),
            'role': user.role.name,
            'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None
        })
    
    def put(self, request):
        """Update the current user's profile information"""
        logger = logging.getLogger(__name__)
        
        try:
            user = request.user
            logger.info(f"Current username before update: {user.username}")
            
            # Check if username is being changed
            if 'username' in request.data:
                new_username = request.data['username'].strip()
                logger.info(f"Attempting to update username to: {new_username}")
                
                # Validate username is not empty
                if not new_username:
                    return Response(
                        {"error": "Username cannot be empty"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate username length (between 3 and 30 characters)
                if len(new_username) < 3 or len(new_username) > 30:
                    return Response(
                        {"error": "Username must be between 3 and 30 characters"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate username contains only allowed characters (letters, numbers, underscores, hyphens)
                if not all(c.isalnum() or c in '_-' for c in new_username):
                    return Response(
                        {"error": "Username can only contain letters, numbers, underscores, and hyphens"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if username is already taken by another user
                if User.objects.exclude(id=user.id).filter(username=new_username).exists():
                    return Response(
                        {"error": "Username is already taken"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Direct database update
                updated = User.objects.filter(id=user.id).update(username=new_username)
                logger.info(f"Database update result: {updated}")
                
                # Force refresh from database
                user = User.objects.get(id=user.id)
                logger.info(f"Username after refresh: {user.username}")
            
            # Update other fields if provided
            if 'email' in request.data:
                user.email = request.data['email']
            if 'first_name' in request.data:
                user.first_name_encrypted = encrypt(request.data['first_name'])
                user.first_name = "***"
            if 'last_name' in request.data:
                user.last_name_encrypted = encrypt(request.data['last_name'])
                user.last_name = "***"
            if 'avatar' in request.data:
                user.avatar = request.data['avatar']
            
            # Save all changes
            user.save()
            logger.info(f"Final username after save: {user.username}")
            
            # One final refresh
            user.refresh_from_db()
            logger.info(f"Final username after final refresh: {user.username}")
            
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.get_decrypted_first_name(),
                'last_name': user.get_decrypted_last_name(),
                'role': user.role.name,
                'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None
            })
            
        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Error updating profile: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_students_from_csv(request, pk):
    csv_file = request.FILES['csv_file']
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()  # Remove extra spaces in headers
    enrolled_user_ids = []
    error_names = []    # names of users not found in the database
    enrolled_names = [] # names of users successfully enrolled in the classroom

    required_cols = {"First Name","Last Name"}
    if not required_cols.issubset(df.columns):
        return Response(
            {"error": f"CSV file must contain the following columns: {', '.join(required_cols)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Preprocess all users: map (lowercased first + last name) to user instance
    user_lookup = {
        f"{(user.get_decrypted_first_name() or '').strip().lower()} {(user.get_decrypted_last_name() or '').strip().lower()}": user
        for user in User.objects.all()
    }
    classroom = Classroom.objects.get(pk=pk)
    classroom_student_lookup = {
        f"{(student.get_decrypted_first_name() or '').strip().lower()} {(student.get_decrypted_last_name() or '').strip().lower()}": student
        for student in classroom.students.all()
    }


    for _, row in df.iterrows():
        first_name = str(row['First Name']).strip()
        last_name = str(row['Last Name']).strip()
        full_name = f"{first_name.lower()} {last_name.lower()}"

        user = user_lookup.get(full_name)
        if user:
            if classroom_student_lookup.get(full_name):
                error_names.append(f"{last_name}, {first_name}")
                print(f"User already enrolled in classroom: {user.username} - {first_name} {last_name}")
                continue

            enrolled_user_ids.append(user.id)
            enrolled_names.append(f"{last_name}, {first_name}")
            print(f"Enrolling existing user: {user.username} - {first_name} {last_name}")
        else:
            error_names.append(f"{last_name}, {first_name}")
            print(f"No user found for: {first_name} {last_name}. Skipping.")

    if (len(enrolled_user_ids) == 0):
        return Response({
            "error": "Names in CSV does not exist.",
            "not-enrolled": error_names
        }, status=status.HTTP_404_NOT_FOUND)
    else:
        classroom.students.add(*enrolled_user_ids)
        # print("Enrolled students:", classroom.students.all())

    return Response({
            "message": f"Enrolled {len(enrolled_user_ids)} students from CSV.",
            "enrolled": enrolled_names,
            "not-enrolled": error_names
        }, status=status.HTTP_202_ACCEPTED)

class IsTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        try:
            return request.user.role.name == 'teacher'
        except (AttributeError, Role.DoesNotExist):
            return False

    def has_object_permission(self, request, view, obj):
        # For transfer requests, check if user is either the requesting teacher or the receiving teacher
        if isinstance(obj, TransferRequest):
            return (request.user == obj.requested_by) or (request.user == obj.to_classroom.teacher)
        return True

class TransferRequestViewSet(viewsets.ModelViewSet):
    serializer_class = TransferRequestSerializer
    permission_classes = [IsAuthenticated, IsTeacher]

    def get_queryset(self):
        user = self.request.user
        # Teachers can see requests they made or received
        return TransferRequest.objects.filter(
            models.Q(requested_by=user) | 
            models.Q(to_classroom__teacher=user)
        )

    def get_permissions(self):
        """
        Override get_permissions to allow any authenticated user to delete their own requests
        """
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsTeacher()]

    def perform_create(self, serializer):
        # Create transfer request
        transfer_request = serializer.save(requested_by=self.request.user)
        
        # Create notification for the receiving teacher
        Notification.objects.create(
            recipient=transfer_request.to_classroom.teacher,
            type='student_transfer',
            message=f"{transfer_request.requested_by.get_decrypted_first_name()} {transfer_request.requested_by.get_decrypted_last_name()} has requested to transfer {transfer_request.student.get_decrypted_first_name()} {transfer_request.student.get_decrypted_last_name()} to your classroom {transfer_request.to_classroom.name}",
            data={
                'transfer_request_id': transfer_request.id,
                'student_id': transfer_request.student.id,
                'student_name': f"{transfer_request.student.get_decrypted_first_name()} {transfer_request.student.get_decrypted_last_name()}",
                'from_classroom_id': transfer_request.from_classroom.id,
                'from_classroom_name': transfer_request.from_classroom.name,
                'to_classroom_id': transfer_request.to_classroom.id,
                'to_classroom_name': transfer_request.to_classroom.name
            }
        )

    def destroy(self, request, *args, **kwargs):
        try:
            transfer_request = self.get_object()
            
            # Check if request is still pending
            if transfer_request.status != 'pending':
                return Response(
                    {"error": f"Cannot delete a request that has been {transfer_request.status}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Delete associated notification
            Notification.objects.filter(
                type='student_transfer',
                data__transfer_request_id=transfer_request.id
            ).delete()
            
            # Delete the transfer request
            transfer_request.delete()
            
            return Response(
                {"message": "Transfer request deleted successfully"},
                status=status.HTTP_200_OK
            )
            
        except TransferRequest.DoesNotExist:
            return Response(
                {"error": "Transfer request not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def available_classrooms(self, request):
        """
        Get all available classrooms for transfer requests.
        Excludes the student's current classroom.
        """
        student_id = request.query_params.get('student_id')
        if not student_id:
            return Response(
                {"error": "student_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = User.objects.get(id=student_id, role__name='student')
            # Get the student's current classroom
            current_classroom = Classroom.objects.filter(students=student).first()
            
            # Get all classrooms except the student's current one
            available_classrooms = Classroom.objects.exclude(id=current_classroom.id if current_classroom else None)
            
            # Serialize the classrooms with request context
            serializer = ClassroomSerializer(available_classrooms, many=True, context={'request': request})
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"error": "Student not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        transfer_request = self.get_object()
        
        # Check if the requesting user is the teacher of the target classroom
        if request.user != transfer_request.to_classroom.teacher:
            return Response(
                {"error": "Only the receiving teacher can approve transfer requests"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update transfer request status
        transfer_request.status = 'approved'
        transfer_request.save()

        # Remove student from current classroom
        transfer_request.from_classroom.students.remove(transfer_request.student)
        
        # Add student to new classroom
        transfer_request.to_classroom.students.add(transfer_request.student)

        # Create notification for the requesting teacher
        Notification.objects.create(
            recipient=transfer_request.requested_by,
            type='transfer_approved',
            message=f"Your request to transfer {transfer_request.student.get_decrypted_first_name()} {transfer_request.student.get_decrypted_last_name()} to {transfer_request.to_classroom.name} has been approved",
            data={
                'transfer_request_id': transfer_request.id,
                'student_id': transfer_request.student.id,
                'student_name': f"{transfer_request.student.get_decrypted_first_name()} {transfer_request.student.get_decrypted_last_name()}",
                'classroom_id': transfer_request.to_classroom.id,
                'classroom_name': transfer_request.to_classroom.name
            }
        )

        return Response({"status": "approved"})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        transfer_request = self.get_object()
        
        # Check if the requesting user is the teacher of the target classroom
        if request.user != transfer_request.to_classroom.teacher:
            return Response(
                {"error": "Only the receiving teacher can reject transfer requests"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update transfer request status
        transfer_request.status = 'rejected'
        transfer_request.save()

        # Create notification for the requesting teacher
        Notification.objects.create(
            recipient=transfer_request.requested_by,
            type='transfer_rejected',
            message=f"Your request to transfer {transfer_request.student.get_decrypted_first_name()} {transfer_request.student.get_decrypted_last_name()} to {transfer_request.to_classroom.name} has been rejected",
            data={
                'transfer_request_id': transfer_request.id,
                'student_id': transfer_request.student.id,
                'student_name': f"{transfer_request.student.get_decrypted_first_name()} {transfer_request.student.get_decrypted_last_name()}",
                'classroom_id': transfer_request.to_classroom.id,
                'classroom_name': transfer_request.to_classroom.name
            }
        )

        return Response({"status": "rejected"})

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def destroy(self, request, *args, **kwargs):
        notification = self.get_object()
        
        # Only allow users to delete their own notifications
        if notification.recipient != request.user:
            return Response(
                {"error": "You can only delete your own notifications"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({"status": "all marked as read"})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_image(request):
    if 'image' not in request.FILES:
        return Response({'error': 'No image file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    image_file = request.FILES['image']
    
    # Validate file type
    if not image_file.content_type.startswith('image/'):
        return Response({'error': 'Invalid file type. Only image files are allowed.'}, 
                        status=status.HTTP_400_BAD_REQUEST)
    
    # Generate a unique filename
    filename = f"vocabulary/images/{os.path.basename(image_file.name)}"
    
    try:
        # Save the file
        saved_path = default_storage.save(filename, image_file)
        
        # Get the URL of the saved file
        file_url = request.build_absolute_uri(default_storage.url(saved_path))
        
        return Response({'url': file_url}, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_video(request):
    if 'video' not in request.FILES:
        return Response({'error': 'No video file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    video_file = request.FILES['video']
    
    # Validate file type
    if not video_file.content_type.startswith('video/'):
        return Response({'error': 'Invalid file type. Only video files are allowed.'}, 
                        status=status.HTTP_400_BAD_REQUEST)
    
    # Generate a unique filename
    filename = f"vocabulary/videos/{os.path.basename(video_file.name)}"
    
    try:
        # Save the file
        saved_path = default_storage.save(filename, video_file)
        
        # Get the URL of the saved file
        file_url = request.build_absolute_uri(default_storage.url(saved_path))
        
        return Response({'url': file_url}, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DrillResultListView(generics.ListAPIView):
    serializer_class = DrillResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        drill_id = self.kwargs['drill_id']
        user = self.request.user
        try:
            drill = Drill.objects.get(id=drill_id)
            
            # Check if user has permission to view results
            if user.role.name == 'teacher' and drill.created_by == user:
                # Teacher can see all results for their drill
                return DrillResult.objects.filter(drill_id=drill_id).select_related('student').prefetch_related('question_results')
            elif user.role.name == 'student' and drill.classroom.students.filter(id=user.id).exists():
                # Student can see all results for drills in their classroom
               return DrillResult.objects.filter(drill_id=drill_id).select_related('student').prefetch_related('question_results')
                # return DrillResult.objects.filter(drill_id=drill_id, student=user).select_related('student').prefetch_related('question_results')
            else:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You do not have permission to view results for this drill.")
        except Drill.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Drill not found.")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

# Add a view to submit answers for a single question
class SubmitAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, drill_id, question_id):
        try:
            user = request.user
            drill = Drill.objects.get(id=drill_id)
            question = DrillQuestion.objects.get(id=question_id, drill=drill)

            # Ensure student is enrolled in the classroom to submit answers
            if user.role.name != 'student' or not drill.classroom.students.filter(id=user.id).exists():
                 from rest_framework.exceptions import PermissionDenied
                 raise PermissionDenied("Only students enrolled in the classroom can submit answers.")

            submitted_answer_data = request.data.get('answer')
            time_taken = request.data.get('time_taken') # Optional time taken for this question
            wrong_attempts = request.data.get('wrong_attempts', 0) # Get wrong attempts from frontend

            if submitted_answer_data is None:
                 return Response({"error": "Answer data is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Get or create the overall DrillResult for this student and drill run
            drill_result, created = DrillResult.objects.get_or_create(
                student=user,
                drill=drill,
                defaults={
                    'run_number': 1,
                    'start_time': timezone.now(),
                    'completion_time': timezone.now(),
                    # 'points': 0
                }
            )

            # If it's not a new drill_result, increment run number and reset points
            if not created:
                drill_result.run_number += 1
                drill_result.completion_time = timezone.now()
                drill_result.points = 0.0  # Reset points for new attempt
                drill_result.save(update_fields=['run_number', 'completion_time', '_points_encrypted'])
            else:
                drill_result.points = 0.0
                drill_result.save(update_fields=['_points_encrypted'])

            # Determine if the answer is correct
            is_correct = self.check_answer(question, submitted_answer_data)

            # Get points from frontend
            points_to_award = request.data.get('points', 0)

            # Create or update the QuestionResult for this specific question
            question_result, created = QuestionResult.objects.update_or_create(
                drill_result=drill_result,
                question=question,
                defaults={
                    'submitted_answer': submitted_answer_data,
                    'is_correct': is_correct,
                    'time_taken': time_taken,
                    'submitted_at': timezone.now(),
                    'points_awarded': points_to_award
                }
            )

            # Update overall points on DrillResult
            #drill_result.points += points_to_award
            total_points_for_run = drill_result.question_results.aggregate(total=models.Sum('points_awarded'))['total'] or 0
            drill_result.points = total_points_for_run
            drill_result.save(update_fields=['_points_encrypted'])

            # Update user's total points and check for badges
            user.update_points_and_badges(total_points_for_run)

            # Get the best score for this drill
            best_score = 0
            drill_results_for_max = DrillResult.objects.filter(
                student=user,
                drill=drill
            ) #.aggregate(best_score=models.Max('points'))['best_score'] or 0
            decrypted_points = [result.points for result in drill_results_for_max if result.points is not None]
            if decrypted_points:
                best_score = max(decrypted_points)
            else:
                best_score = 0


            return Response({
                'success': True,
                'question_result_id': question_result.id,
                'is_correct': is_correct,
                'submitted_answer': question_result.submitted_answer,
                'points_awarded': points_to_award,
                'current_points': drill_result.points,
                'best_score': best_score,
                'run_number': drill_result.run_number
            }, status=status.HTTP_201_CREATED)

        except Drill.DoesNotExist:
            return Response({"error": "Drill not found"}, status=status.HTTP_404_NOT_FOUND)
        except DrillQuestion.DoesNotExist:
            return Response({"error": "Question not found in this drill"}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            import traceback
            print(f"SubmitAnswerView Error: {e}\n{traceback.format_exc()}")
            return Response({"error": str(e), "traceback": traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def check_answer(self, question, submitted_answer_data):
        """Helper method to check if the submitted answer is correct."""
        if question.type == 'M': # Multiple Choice
            # Submitted answer is the index of the chosen option
            try:
                submitted_index = int(submitted_answer_data)
                # Get the correct choice index from the question's answer field
                correct_index = int(question.answer) if question.answer is not None else None
                print(f"Multiple Choice - Submitted: {submitted_index}, Correct: {correct_index}, Question ID: {question.id}")  # Debug log
                return submitted_index == correct_index
            except (ValueError, TypeError) as e:
                print(f"Multiple Choice Error: {e}, Question ID: {question.id}")  # Debug log
                return False

        elif question.type == 'F': # Fill in the Blank
            try:
                submitted_index = int(submitted_answer_data)
                # Get the correct choice index from the question's answer field
                correct_index = int(question.answer) if question.answer is not None else None
                print(f"Fill in Blank - Submitted: {submitted_index}, Correct: {correct_index}, Question ID: {question.id}")  # Debug log
                return submitted_index == correct_index
            except (ValueError, TypeError) as e:
                print(f"Fill in Blank Error: {e}, Question ID: {question.id}")  # Debug log
                return False

        elif question.type == 'D': # Drag and Drop
            # Submitted answer is likely a mapping of drop zone index to drag item index
            # Example submitted_answer_data: { "0": 2, "1": 0 } (Drop Zone 0 got Drag Item 2, Drop Zone 1 got Drag Item 0)
            # The correct mapping is stored in question.dropZones (correctItemIndex for each zone)
            if isinstance(submitted_answer_data, dict) and question.dropZones:
                 is_correct = True
                 for i, drop_zone in enumerate(question.dropZones):
                     submitted_item_index = submitted_answer_data.get(str(i)) # Get submitted item index for this drop zone index (key is string)
                     correct_item_index = drop_zone.get('correctItemIndex')

                     # Check if submitted index matches correct index for this drop zone
                     if submitted_item_index is None or submitted_item_index != correct_item_index:
                         is_correct = False
                         break # No need to check further if one mapping is incorrect
                 return is_correct
            return False

        elif question.type == 'G': # Memory Game
            # For memory game, we just need to check if all cards are matched
            # The frontend sends an array of card IDs that are matched
            if isinstance(submitted_answer_data, list) and question.memoryCards:
                # Check if we have the correct number of matches
                # Each pair should have 2 cards, so total matches should be half the number of cards
                expected_matches = len(question.memoryCards) // 2
                if len(submitted_answer_data) != expected_matches * 2:
                    return False
                
                # Check if all cards are matched (no duplicates)
                unique_cards = set(submitted_answer_data)
                if len(unique_cards) != len(submitted_answer_data):
                    return False
                
                # Check if all cards from memoryCards are included
                memory_card_ids = set()
                for card in question.memoryCards:
                    if card.get('id'):
                        memory_card_ids.add(str(card['id']))
                
                submitted_card_ids = set(submitted_answer_data)
                return memory_card_ids == submitted_card_ids

            return False

        elif question.type == 'P': # Picture Word
            # Submitted answer is likely the text word entered by the student
            # The correct answer is stored in the question's `answer` field
            if isinstance(submitted_answer_data, str) and question.answer:
                return submitted_answer_data.strip().lower() == question.answer.strip().lower()
            return False

        # Handle other question types or return False by default
        return False

class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role.name == 'teacher':
            return Badge.objects.all()
        return user.badges.all()

    @action(detail=False, methods=['get'])
    def student_badges(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return Response({'error': 'student_id is required'}, status=400)
        
        try:
            student = User.objects.get(id=student_id, role__name='student')
            if request.user.role.name == 'teacher' or request.user.id == student.id:
                badges = student.badges.all()
                serializer = self.get_serializer(badges, many=True)
                return Response(serializer.data)
            return Response({'error': 'Not authorized to view these badges'}, status=403)
        except User.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

    @action(detail=False, methods=['get'])
    def badge_statistics(self, request):
        user = request.user
        if user.role.name == 'teacher':
            # Get statistics for all students
            total_badges = Badge.objects.count()
            students_with_badges = User.objects.filter(role__name='student', badges__isnull=False).distinct().count()
            total_students = User.objects.filter(role__name='student').count()
            return Response({
                'total_badges': total_badges,
                'students_with_badges': students_with_badges,
                'total_students': total_students,
                'badge_completion_rate': (students_with_badges / total_students * 100) if total_students > 0 else 0
            })
        else:
            # Get statistics for the current student
            earned_badges = user.badges.count()
            total_badges = Badge.objects.count()
            return Response({
                'earned_badges': earned_badges,
                'total_badges': total_badges,
                'badge_completion_rate': (earned_badges / total_badges * 100) if total_badges > 0 else 0
            })

    @action(detail=False, methods=['get'])
    def points_statistics(self, request):
        user = request.user
        if user.role.name == 'teacher':
            # Get points statistics for all students
            students = User.objects.filter(role__name='student')
            total_points = students.aggregate(total=Sum('total_points'))['total'] or 0
            avg_points = students.aggregate(avg=Avg('total_points'))['avg'] or 0
            max_points = students.aggregate(max=Max('total_points'))['max'] or 0
            return Response({
                'total_points': total_points,
                'average_points': avg_points,
                'max_points': max_points,
                'total_students': students.count()
            })
        else:
            # Get points statistics for the current student
            return Response({
                'total_points': user.total_points,
                'points_to_next_badge': self._get_points_to_next_badge(user)
            })

    @action(detail=False, methods=['get'])
    def all_student_points(self, request):
        """
        Get points for students:
        - Teachers can see all students' points
        - Students can only see their own points
        """
        # First check if user is authenticated
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Then check if user has a role
        if not hasattr(request.user, 'role'):
            return Response(
                {'error': 'User has no role assigned'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            if request.user.role.name == 'teacher':
                # Teachers can see all students
                students = User.objects.filter(role__name='student')
                student_points_data = []
                for student in students:
                    # Calculate total points from all drills across all classrooms


                    # This fetches the _points_encrypted binary field from the DB
                    student_drill_results = DrillResult.objects.filter(student=student)

                    total_points = sum(result.points for result in student_drill_results if result.points is not None)
                    
                    # Get points breakdown by classroom
                    classroom_points_data  = []
                    for classroom in Classroom.objects.filter(students=student):
                        classroom_drill_results  = DrillResult.objects.filter(
                            student=student,
                            drill__classroom=classroom
                        )
                        # Calculate classroom total
                        classroom_total = sum(result.points for result in classroom_drill_results if result.points is not None)
                        
                        
                        classroom_points_data.append({
                            'classroom_id': classroom.id,
                            'classroom_name': classroom.name,
                            'points': classroom_total
                        })
                    
                    student_points_data.append({
                        'id': student.id,
                        'first_name': student.get_decrypted_first_name(),
                        'last_name': student.get_decrypted_last_name(),
                        'avatar': request.build_absolute_uri(student.avatar.url) if student.avatar else None,
                        'total_points': total_points,
                        'classroom_points': classroom_points_data,
                        'badges_count': student.badges.count()
                    })
                
                # Sort by total points in descending order
                student_points_data.sort(key=lambda x: x['total_points'], reverse=True)
                return Response(student_points_data)
            else:
                # Students can only see themselves
                student = request.user

                student_drill_results = DrillResult.objects.filter(student=student)
                
                # Calculate total points
                total_points = sum(result.points for result in student_drill_results if result.points is not None)
                
                
                # Get points breakdown by classroom
                classroom_points_data = []
                for classroom in Classroom.objects.filter(students=student):
                    classroom_drill_results = DrillResult.objects.filter(
                        student=student,
                        drill__classroom=classroom
                    )
                    # Calculate classroom total in Python
                    classroom_total = sum(result.points for result in classroom_drill_results if result.points is not None)
                    
                    classroom_points_data.append({
                        'classroom_id': classroom.id,
                        'classroom_name': classroom.name,
                        'points': classroom_total
                    })
                
                return Response({
                    'id': student.id,
                    'first_name': student.get_decrypted_first_name(),
                    'last_name': student.get_decrypted_last_name(),
                    'avatar': request.build_absolute_uri(student.avatar.url) if student.avatar else None,
                    'total_points': total_points,
                    'classroom_points': classroom_points_data,
                    'badges_count': student.badges.count()
                })
            
        except Exception as e:
            return Response(
                {'error': f'Error retrieving student points: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_points_to_next_badge(self, user):
        """Helper method to calculate points needed for next badge"""
        current_points = user.total_points
        next_badge = Badge.objects.filter(
            points_required__gt=current_points,
            is_first_drill=False
        ).order_by('points_required').first()
        
        if next_badge:
            return next_badge.points_required - current_points
        return 0

    @action(detail=False, methods=['get'])
    def earned_badges(self, request):
        """
        Get detailed information about earned badges.
        For students: shows their earned badges with progress
        For teachers: shows all badges with student earning statistics
        """
        user = request.user
        
        if user.role.name == 'teacher':
            # Get all badges with earning statistics
            badges = Badge.objects.all()
            badge_data = []
            
            for badge in badges:
                # Count how many students have earned this badge
                earned_count = User.objects.filter(badges=badge).count()
                total_students = User.objects.filter(role__name='student').count()
                
                badge_data.append({
                    'id': badge.id,
                    'name': badge.name,
                    'description': badge.description,
                    'image': request.build_absolute_uri(badge.image.url) if badge.image else None,
                    'points_required': badge.points_required,
                    'is_first_drill': badge.is_first_drill,
                    'drills_completed_required': badge.drills_completed_required,
                    'correct_answers_required': badge.correct_answers_required,
                    'earned_count': earned_count,
                    'total_students': total_students,
                    'completion_rate': (earned_count / total_students * 100) if total_students > 0 else 0
                })
            
            return Response(badge_data)
        else:
            # For students, show their earned badges with progress
            earned_badges = user.badges.all()
            all_badges = Badge.objects.all()
            
            # Create a set of earned badge IDs for quick lookup
            earned_badge_ids = set(earned_badges.values_list('id', flat=True))
            
            badge_data = []
            for badge in all_badges:
                # Calculate progress for each badge
                progress = None
                if badge.points_required:
                    progress = min(100, (user.total_points / badge.points_required * 100))
                elif badge.drills_completed_required:
                    completed_drills = DrillResult.objects.filter(student=user).count()
                    progress = min(100, (completed_drills / badge.drills_completed_required * 100))
                elif badge.correct_answers_required:
                    correct_answers = QuestionResult.objects.filter(
                        drill_result__student=user,
                        is_correct=True
                    ).count()
                    progress = min(100, (correct_answers / badge.correct_answers_required * 100))
                
                badge_data.append({
                    'id': badge.id,
                    'name': badge.name,
                    'description': badge.description,
                    'image': request.build_absolute_uri(badge.image.url) if badge.image else None,
                    'points_required': badge.points_required,
                    'is_first_drill': badge.is_first_drill,
                    'drills_completed_required': badge.drills_completed_required,
                    'correct_answers_required': badge.correct_answers_required,
                    'is_earned': badge.id in earned_badge_ids,
                    'progress': progress,
                    'earned_at': user.badges.through.objects.filter(
                        user=user,
                        badge=badge
                    ).first().created_at if badge.id in earned_badge_ids else None
                })
            
            return Response(badge_data)

    @action(detail=False, methods=['get'])
    def drill_statistics(self, request):
        """
        Get statistics about student's drill performance.
        For students: shows their own statistics
        For teachers: can view any student's statistics by providing student_id
        """
        try:
            # Get the target student
            student_id = request.query_params.get('student_id')
            if student_id and request.user.role.name == 'teacher':
                student = User.objects.get(id=student_id, role__name='student')
            else:
                student = request.user
                if student.role.name != 'student':
                    return Response(
                        {"error": "Only students can view their own statistics"}, 
                        status=status.HTTP_403_FORBIDDEN
                    )

            # Get total completed drills (unique drills attempted)
            completed_drills = DrillResult.objects.filter(
                student=student
            ).values('drill').distinct().count()

            # Get total correct answers
            correct_answers = QuestionResult.objects.filter(
                drill_result__student=student,
                is_correct=True
            ).count()

            # Get total questions attempted
            total_questions = QuestionResult.objects.filter(
                drill_result__student=student
            ).count()

            # Calculate accuracy percentage
            accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0

            # Get statistics by classroom
            classroom_stats = []
            for classroom in Classroom.objects.filter(students=student):
                classroom_drills = DrillResult.objects.filter(
                    student=student,
                    drill__classroom=classroom
                ).values('drill').distinct().count()

                classroom_correct = QuestionResult.objects.filter(
                    drill_result__student=student,
                    drill_result__drill__classroom=classroom,
                    is_correct=True
                ).count()

                classroom_total = QuestionResult.objects.filter(
                    drill_result__student=student,
                    drill_result__drill__classroom=classroom
                ).count()

                classroom_accuracy = (classroom_correct / classroom_total * 100) if classroom_total > 0 else 0

                classroom_stats.append({
                    'classroom_id': classroom.id,
                    'classroom_name': classroom.name,
                    'completed_drills': classroom_drills,
                    'correct_answers': classroom_correct,
                    'total_questions': classroom_total,
                    'accuracy': classroom_accuracy
                })

            return Response({
                'student_id': student.id,
                'student_name': f"{student.get_decrypted_first_name()} {student.get_decrypted_last_name()}",
                'total_completed_drills': completed_drills,
                'total_correct_answers': correct_answers,
                'total_questions_attempted': total_questions,
                'overall_accuracy': accuracy,
                'classroom_statistics': classroom_stats
            })

        except User.DoesNotExist:
            return Response(
                {"error": "Student not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error retrieving drill statistics: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
