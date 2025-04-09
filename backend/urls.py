from django.contrib import admin
from django.urls import path, include
from api.views import CreateUserView, UserListView, CustomTokenView, CheckUsernameView
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
]
