from django.shortcuts import render
from .models import User, PasswordReset, Classroom, Drill, DrillQuestion, DrillResult, MemoryGameResult, TransferRequest, Notification
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import generics, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, CustomTokenSerializer, ResetPasswordRequestSerializer, ResetPasswordSerializer, ClassroomSerializer, DrillSerializer, TransferRequestSerializer, NotificationSerializer
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
from api.utils.encryption import decrypt  # Import the decrypt function
from cryptography.fernet import InvalidToken  # Import the InvalidToken exception
from django.utils import timezone
from django.db import models

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
            drill_result.points = score
            drill_result.save()
            
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
        user = request.user
        
        # Update fields if provided
        if 'email' in request.data:
            user.email = request.data['email']
        if 'first_name' in request.data:
            user.first_name = request.data['first_name']
        if 'last_name' in request.data:
            user.last_name = request.data['last_name']
        if 'avatar' in request.data:
            user.avatar = request.data['avatar']
            
        user.save()
        
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.get_decrypted_first_name(),
            'last_name': user.get_decrypted_last_name(),
            'role': user.role.name,
            'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_students_from_csv(request, pk):
    csv_file = request.FILES['csv_file']
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()  # Remove extra spaces in headers
    enrolled_user_ids = []

    for _, row in df.iterrows():
        first_name = str(row['First Name']).strip()
        last_name = str(row['Last Name']).strip()
        
        # Try to decrypt the first and last names
        try:
            decrypted_first_name = decrypt(first_name) if first_name else None
            decrypted_last_name = decrypt(last_name) if last_name else None
        except InvalidToken:
            # If decryption fails, use the plain text values
            decrypted_first_name = first_name
            decrypted_last_name = last_name
        
        # Find existing user by decrypted first and last name (case-insensitive)
        for user in User.objects.all():
            if (user.get_decrypted_first_name() or '').strip().lower() == first_name.lower() and \
               (user.get_decrypted_last_name() or '').strip().lower() == last_name.lower():
                enrolled_user_ids.append(user.id)
                print(f"Enrolling existing user: {user.username}")
                break
        else:
            print(f"No user found for: {first_name} {last_name}. Skipping.")

    classroom = Classroom.objects.get(pk=pk)
    classroom.students.add(*enrolled_user_ids)
    print("Enrolled students:", classroom.students.all())

    return Response({"success": f"Enrolled {len(enrolled_user_ids)} students from CSV."})
  
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
            drill_result.points = score
            drill_result.save()
            
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
