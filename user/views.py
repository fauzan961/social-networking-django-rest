from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.pagination import PageNumberPagination
from .models import CustomUser
from friend_requests.models import BlockList
from .serializers import UserSerializer
from django.core.exceptions import ValidationError
from django.db.models import Q, Subquery
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.contrib.auth import authenticate
from django.core.validators import EmailValidator
from django.contrib.auth.password_validation import validate_password
from rest_framework.throttling import AnonRateThrottle
from rest_framework.permissions import IsAuthenticated

class SignupView(APIView):
    def post(self, request):
        email = request.data.get('email', '').lower()
        password = request.data.get('password', '')
        
        email_validation_error = self.validate_email(email)
        if email_validation_error:
            return Response({'error': email_validation_error}, status=status.HTTP_400_BAD_REQUEST)

        password_validation_error = self.validate_password(password)
        if password_validation_error:
            return Response({'error': password_validation_error}, status=status.HTTP_400_BAD_REQUEST)
        
        if CustomUser.objects.filter(email=email).exists():
            return Response({'error': 'Email is already registered'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            CustomUser.objects.create_user(email=email, password=password)
        except Exception as e:
            return Response({'error': 'User creation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({'message': 'User created successfully'}, status=status.HTTP_201_CREATED)
    
    def validate_email(self, email):
        email_validator = EmailValidator()
        try:
            email_validator(email)
            return None
        except ValidationError:
            return 'Invalid email address'

    def validate_password(self, password):
        try:
            validate_password(password)
            return None
        except ValidationError as e:
            return e.messages

class LoginView(APIView):
    throttle_classes = [AnonRateThrottle]
    
    def post(self, request):
        email = request.data.get('email', '').lower()
        password = request.data.get('password')
        user = authenticate(email=email, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        return Response({'error': 'Invalid credentials here'}, status=status.HTTP_401_UNAUTHORIZED)
    
class UserSearchPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class UserSearchView(APIView):
    pagination_class = UserSearchPagination
    permission_classes = [IsAuthenticated]  

    def get(self, request):
        keyword = request.query_params.get('q', '').strip()
        if not keyword:
            return Response({'error': 'No search keyword provided'}, status=400)
        
        # Excluding the blocked users
        blocked_by_user_subquery = BlockList.objects.filter(blocker=request.user).values('blocked_id')
        blocked_user_subquery = BlockList.objects.filter(blocked=request.user).values('blocker_id')
        excluded_users = Q(id__in=Subquery(blocked_by_user_subquery)) | Q(id__in=Subquery(blocked_user_subquery))

        # If it's an exact email match
        if '@' in keyword:
            user = CustomUser.objects.filter(email__iexact=keyword).exclude(excluded_users).first()
            if user:
                serializer = UserSerializer(user)
                return Response(serializer.data)
            else:
                return Response({'message': 'No user found with that email'}, status=404)

        # Full-text search for name
        search_vector = SearchVector('name')
        search_query = SearchQuery(keyword)
        results = CustomUser.objects.annotate(rank=SearchRank(search_vector, search_query))\
                                    .filter(Q(name__icontains=keyword))\
                                    .exclude(excluded_users)\
                                    .order_by('-rank')

        # Paginate the results
        paginator = UserSearchPagination()
        paginated_results = paginator.paginate_queryset(results, request)
        serializer = UserSerializer(paginated_results, many=True)
        return paginator.get_paginated_response(serializer.data)
