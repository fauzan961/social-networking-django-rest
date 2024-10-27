from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from .models import FriendRequest, RejectedFriendRequest, BlockList
from rest_framework.pagination import PageNumberPagination
from user.models import CustomUser
from user.serializers import UserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.core.cache import cache

class FriendRequestThrottle(UserRateThrottle):
    rate = '3/min'  # Limit to 3 friend requests per minute

class SendFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FriendRequestThrottle]

    def post(self, request):
        to_user_id = request.data.get('to_user_id')
        from_user = request.user
        
        try:
            to_user = CustomUser.objects.get(id=to_user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User does not exist'}, status=status.HTTP_404_NOT_FOUND)

        if from_user == to_user:
            return Response({'error': 'You cannot send a friend request to yourself'}, status=status.HTTP_400_BAD_REQUEST)
        
        if FriendRequest.objects.filter(from_user=to_user, to_user=from_user).exists():
            return Response({'error': 'Friend request already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if self.is_blocked(from_user, to_user):
            return Response({'error': 'Cannot send request, User Blocked.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if self.if_rejected_recently(from_user, to_user):
            return Response({'error': 'Friend request was recently rejected. Try again later.'}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            friend_request, created = FriendRequest.objects.get_or_create(from_user=from_user, to_user=to_user)

        if not created:
            return Response({'error': 'Friend request already sent'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Friend request sent successfully'}, status=status.HTTP_201_CREATED)
    
    def if_rejected_recently(self, from_user, to_user):
        cooldown_period = getattr(settings, 'FRIEND_REQUEST_COOLDOWN_PERIOD', 86400)
        
        return RejectedFriendRequest.objects.filter(
            from_user=from_user,
            to_user=to_user,
            timestamp__gte=timezone.now() - timedelta(seconds=cooldown_period)
        ).exists()
        
    def is_blocked(self, from_user, to_user):
        return BlockList.objects.filter(
        Q(blocker=from_user, blocked=to_user) | Q(blocker=to_user, blocked=from_user)
        ).exists()


class ConfirmFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]  

    def post(self, request, friend_request_id):
        req_status = request.data.get('status', 'pending')
        try:
            with transaction.atomic():
                friend_request = FriendRequest.objects.select_for_update().get(id=friend_request_id, to_user=request.user)
        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request does not exist'}, status=status.HTTP_404_NOT_FOUND)

        if req_status == 'rejected':
            self.reject_friend_request(friend_request)
        else:   
            friend_request.status = req_status
            friend_request.save()

        return Response({'message': f'Friend request {req_status}'}, status=status.HTTP_200_OK)
    
    def reject_friend_request(self, friend_request):
        friend_request.delete()
        RejectedFriendRequest.objects.create(from_user=friend_request.from_user, to_user=friend_request.to_user)
        
        
class BlockUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        to_block_id = request.data.get('blocked_user_id')
        blocker = request.user
        
        try:
            to_block = CustomUser.objects.get(id=to_block_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User does not exist'}, status=status.HTTP_404_NOT_FOUND)
        
        if blocker == to_block:
            return Response({'error': 'You cannot block yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                block_entry, created = BlockList.objects.get_or_create(
                    blocker=blocker, 
                    blocked=to_block
                )
                if not created:
                    return Response({'error': 'You have already blocked this user.'}, status=status.HTTP_400_BAD_REQUEST)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        self.delete_friend_request(blocker, to_block)
        return Response({'message': 'User successfully blocked.'}, status=status.HTTP_201_CREATED)
    
    def delete_friend_request(self, from_user, to_user):
        FriendRequest.objects.filter((Q(from_user=from_user, to_user=to_user) | 
                                      Q(from_user=to_user, to_user=from_user))).delete()
        
class UnblockUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        to_unblock_id = request.data.get('blocked_user_id')
        blocker = request.user
        
        try:
            to_unblock = CustomUser.objects.get(id=to_unblock_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User does not exist'}, status=status.HTTP_404_NOT_FOUND)
        
        if blocker == to_unblock:
            return Response({'error': 'You cannot unblock yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                block_entry = BlockList.objects.get(
                    blocker=blocker, 
                    blocked=to_unblock
                )
                block_entry.delete()
                
        except BlockList.DoesNotExist:
            return Response({'error': 'You have not blocked this user.'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'message': 'User unblocked.'}, status=status.HTTP_200_OK)

class BlockView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        cache_key = f"block_list_{user.id}"
        cached_block_list = cache.get(cache_key)
        
        if cached_block_list is not None:
            block_users = cached_block_list
        
        else:
            block_list = BlockList.objects.filter(blocker=user).select_related('blocked')
            block_users = [block.blocked for block in block_list]
            cache.set(cache_key, block_users, timeout=60 * 10)

        paginator = ListPagination()
        result_page = paginator.paginate_queryset(block_users, request)
        serializer = UserSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
        
class ListPagination(PageNumberPagination):
    page_size = 20

class FriendListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = ListPagination

    def get(self, request):
        user = request.user
        cache_key = f"friend_list_{user.id}"
        cached_friends = cache.get(cache_key)
        
        if cached_friends is not None:
            friends = cached_friends
        
        else:
            friend_requests = FriendRequest.objects.filter(
                (Q(from_user=user) | Q(to_user=user)),
                status='accepted'
            ).select_related('from_user', 'to_user')

            friends = [
                friend_request.to_user if friend_request.from_user == user else friend_request.from_user
                for friend_request in friend_requests
            ]
            cache.set(cache_key, friends, timeout=60 * 10)

        paginator = ListPagination()
        result_page = paginator.paginate_queryset(friends, request)
        serializer = UserSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
class PendingRequestListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = ListPagination

    def get(self, request):
        user = request.user
        cache_key = f"req_list_{user.id}"
        cached_requests = cache.get(cache_key)
        sort_order = request.query_params.get('sort', 'desc')
        
        if cached_requests is not None:
            friend_requests = cached_requests
        
        else:
            friend_requests = list(FriendRequest.objects.filter(
                to_user=user,
                status='pending'
            ).select_related('from_user'))
            
            cache.set(cache_key, friend_requests, timeout=60 * 10)
        
        
        friend_requests = sorted(friend_requests, key=lambda p: p.timestamp, reverse=sort_order == 'desc')
        pending_requests = [friend_request.from_user for friend_request in friend_requests]
        paginator = ListPagination()
        result_page = paginator.paginate_queryset(pending_requests, request)
        serializer = UserSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)