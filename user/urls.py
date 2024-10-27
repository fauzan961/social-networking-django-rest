from django.urls import path
from .views import SignupView, LoginView, UserSearchView

urlpatterns = [
    path('login/', LoginView.as_view(), name='signup'),
    path('signup/', SignupView.as_view(), name='login'),
    path('search/', UserSearchView.as_view(), name='user-search')
]

