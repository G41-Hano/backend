from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from api.views import (
    CreateUserView, UserListView, CheckUsernameView, CustomTokenView,
    RequestPasswordReset, ResetPassword, ClassroomListView, ClassroomDetailView,
    ClassroomStudentsView, JoinClassroomView, DrillListCreateView, DrillRetrieveUpdateDestroyView,
    ProfileView, import_students_from_csv,
    TransferRequestViewSet, NotificationViewSet, DrillResultListView, SubmitAnswerView, BadgeViewSet, upload_image, upload_video
)
from api.viewsets.word_list import WordListView
from api.viewsets.builtin_word_list import BuiltInWordListView, BuiltInWordListIndexView
from api.viewsets.gen_ai import GenAIView, GenAICheckLimitView
from rest_framework_simplejwt.views import TokenRefreshView

# API endpoints
urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/userlist/", UserListView.as_view(), name="users"),
    path("api/user/register/", CreateUserView.as_view(), name="register"),
    path("api/user/check-username/", CheckUsernameView.as_view(), name="check_username"),
    path("api/token/", CustomTokenView.as_view(), name="get_token"),
    path("api/token/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("api-auth/", include("rest_framework.urls")),
    path('api/password-reset/', RequestPasswordReset.as_view(), name='password_reset_request'),
    path('api/reset-password/<str:token>/', ResetPassword.as_view(), name='password_reset'),

    # Profile URLs
    path('api/profile/', ProfileView.as_view(), name='profile'),
    
    # Classroom URLs
    path('api/classrooms/', ClassroomListView.as_view(), name='classroom_list'),
    path('api/classrooms/<int:pk>/', ClassroomDetailView.as_view(), name='classroom_detail'),
    path('api/classrooms/<int:pk>/students/', ClassroomStudentsView.as_view(), name='classroom_students'),
    path('api/classrooms/<int:pk>/leaderboard/', ClassroomStudentsView.as_view(), name='classroom_leaderboard'),
    path('api/classrooms/join/', JoinClassroomView.as_view(), name='join_classroom'),
    path('api/classrooms/<int:pk>/import-students/', import_students_from_csv, name='import_students_from_csv'),
    
    # Drill URLs
    path('api/drills/', DrillListCreateView.as_view(), name='drill_list_create'),
    path('api/drills/<int:pk>/', DrillRetrieveUpdateDestroyView.as_view(), name='drill_detail'),
    path('api/drills/<int:drill_id>/results/', DrillResultListView.as_view(), name='drill_results_list'),
    path('api/drills/<int:drill_id>/questions/<int:question_id>/submit/', SubmitAnswerView.as_view(), name='submit_answer'),
    
    # Transfer Request URLs
    path('api/transfer-requests/', TransferRequestViewSet.as_view({'get': 'list', 'post': 'create'}), name='transfer_request_list'),
    path('api/transfer-requests/<int:pk>/', TransferRequestViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='transfer_request_detail'),
    path('api/transfer-requests/<int:pk>/approve/', TransferRequestViewSet.as_view({'post': 'approve'}), name='transfer_request_approve'),
    path('api/transfer-requests/<int:pk>/reject/', TransferRequestViewSet.as_view({'post': 'reject'}), name='transfer_request_reject'),
    path('api/transfer-requests/available-classrooms/', TransferRequestViewSet.as_view({'get': 'available_classrooms'}), name='transfer_request_available_classrooms'),
    
    # Notification URLs
    path('api/notifications/', NotificationViewSet.as_view({'get': 'list'}), name='notification_list'),
    path('api/notifications/<int:pk>/', NotificationViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'}), name='notification_detail'),
    path('api/notifications/<int:pk>/mark-as-read/', NotificationViewSet.as_view({'post': 'mark_as_read'}), name='notification_mark_as_read'),
    path('api/notifications/mark-all-as-read/', NotificationViewSet.as_view({'post': 'mark_all_as_read'}), name='notification_mark_all_as_read'),

    # Built-in Word List URLs
    path('api/builtin-wordlist/', BuiltInWordListIndexView.as_view(), name='builtin-wordlist-index'),
    path('api/builtin-wordlist/<str:list_id>/', BuiltInWordListView.as_view(), name='builtin-wordlist'),

    # Custom Word List URLs
    path('api/wordlist/', WordListView.as_view({'get':'list', 'post':'create'}), name='wordlist_list'),
    path('api/wordlist/<int:pk>/', WordListView.as_view({'get':'retrieve', 'put':'update', 'delete':'destroy'}), name='wordlist_detail'),

    # Gen. AI URL
    path('api/gen-ai/checklimit/', GenAICheckLimitView.as_view(), name='gen-ai-checklimit'),
    path('api/gen-ai/', GenAIView.as_view(), name='gen-ai'),

    # Badge URLs
    path('api/badges/', BadgeViewSet.as_view({'get': 'list'}), name='badge_list'),
    path('api/badges/<int:pk>/', BadgeViewSet.as_view({'get': 'retrieve'}), name='badge_detail'),
    path('api/badges/student-badges/', BadgeViewSet.as_view({'get': 'student_badges'}), name='badge_student_badges'),
    path('api/badges/statistics/', BadgeViewSet.as_view({'get': 'badge_statistics'}), name='badge_statistics'),
    path('api/badges/points-statistics/', BadgeViewSet.as_view({'get': 'points_statistics'}), name='points_statistics'),
    path('api/badges/all-student-points/', BadgeViewSet.as_view({'get': 'all_student_points'}), name='all_student_points'),

    # Upload Image and Video URLs
    path('api/upload-image/', upload_image, name='upload_image'),
    path('api/upload-video/', upload_video, name='upload_video'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
