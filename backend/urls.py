from django.contrib import admin
from django.urls import path, include
from api.views import (
    CreateUserView, UserListView, CheckUsernameView, CustomTokenView,
    RequestPasswordReset, ResetPassword, ClassroomListView, ClassroomDetailView,
    ClassroomStudentsView
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

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
    
    # Classroom URLs
    path('api/classrooms/', ClassroomListView.as_view(), name='classroom_list'),
    path('api/classrooms/<int:pk>/', ClassroomDetailView.as_view(), name='classroom_detail'),
    path('api/classrooms/<int:pk>/students/', ClassroomStudentsView.as_view(), name='classroom_students'),
]
