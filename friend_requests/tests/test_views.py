from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status
from user.models import CustomUser
from ..models import FriendRequest, RejectedFriendRequest, BlockList
from django.core.cache import cache

class FriendRequestTestCase(APITestCase):

    def setUp(self):
        # Create users
        self.user1 = CustomUser.objects.create_user(email='user1@example.com', password='password123')
        self.user2 = CustomUser.objects.create_user(email='user2@example.com', password='password123')
        self.user3 = CustomUser.objects.create_user(email='user3@example.com', password='password123')
        
        # Friend Request URL
        self.send_request_url = reverse('send_friend_request')
        self.block_user_url = reverse('block_user')
        self.unblock_user_url = reverse('unblock_user')
        self.friend_list_url = reverse('friend_list')
        self.pending_request_list_url = reverse('request_list')
        self.block_list_url = reverse('block_list')
        
        # Clear cache before each test
        cache.clear()

    def authenticate(self, user):
        self.client.force_authenticate(user=user)
        
    def test_send_friend_request(self):
        self.authenticate(self.user1)
        
        response = self.client.post(self.send_request_url, {'to_user_id': self.user2.id})
        self.client.post(self.send_request_url, {'to_user_id': self.user3.id})
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FriendRequest.objects.filter(from_user=self.user1).count(), 2)
        
        
    def test_cannot_send_friend_request_to_self(self):
        self.authenticate(self.user1)
        
        response = self.client.post(self.send_request_url, {'to_user_id': self.user1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('You cannot send a friend request to yourself', response.data['error'])
        
    def test_reject_friend_request(self):
        friend_request = FriendRequest.objects.create(from_user=self.user1, to_user=self.user2)
        self.authenticate(self.user2)
        confirm_request_url = reverse('accept_friend_request', args=[friend_request.id])
        
        response = self.client.post(confirm_request_url, {'status': 'rejected'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(FriendRequest.objects.filter(from_user=self.user1, to_user=self.user2).count(), 0)
        self.assertEqual(RejectedFriendRequest.objects.filter(from_user=self.user1, to_user=self.user2).count(), 1)
        
    
    def test_cannot_reject_others_friend_request(self):
        friend_request = FriendRequest.objects.create(from_user=self.user1, to_user=self.user2)
        self.authenticate(self.user3)
        confirm_request_url = reverse('accept_friend_request', args=[friend_request.id])
        
        response = self.client.post(confirm_request_url, {'status': 'rejected'})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Friend request does not exist', response.data['error'])
        self.assertEqual(FriendRequest.objects.filter(from_user=self.user1, to_user=self.user2).count(), 1)
        self.assertEqual(RejectedFriendRequest.objects.filter(from_user=self.user1, to_user=self.user2).count(), 0)
    
    def test_accept_friend_request(self):
        friend_request = FriendRequest.objects.create(from_user=self.user2, to_user=self.user3)
        self.authenticate(self.user3)
        confirm_request_url = reverse('accept_friend_request', args=[friend_request.id])
        
        response = self.client.post(confirm_request_url, {'status': 'accepted'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(FriendRequest.objects.filter(from_user=self.user2, to_user=self.user3).count(), 1)
        
    def test_cannot_accept_others_friend_request(self):
        friend_request = FriendRequest.objects.create(from_user=self.user2, to_user=self.user3)
        self.authenticate(self.user2)
        confirm_request_url = reverse('accept_friend_request', args=[friend_request.id])
        
        response = self.client.post(confirm_request_url, {'status': 'accepted'})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Friend request does not exist', response.data['error'])
        
    def test_block_user(self):
        self.authenticate(self.user1)
        
        response = self.client.post(self.block_user_url, {'blocked_user_id': self.user2.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BlockList.objects.filter(blocker=self.user1, blocked=self.user2).count(), 1)
        
        # Try blocking again
        response = self.client.post(self.block_user_url, {'blocked_user_id': self.user2.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('You have already blocked this user', response.data['error'])
        
        # Cannot block yourself
        response = self.client.post(self.block_user_url, {'blocked_user_id': self.user1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('You cannot block yourself.', response.data['error'])
        
    def test_unblock_user(self):
        self.authenticate(self.user1)
        
        BlockList.objects.create(blocker=self.user1, blocked=self.user2)
        response = self.client.post(self.unblock_user_url, {'blocked_user_id': self.user2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BlockList.objects.filter(blocker=self.user1, blocked=self.user2).count(), 0)
        
        # Try unblocking again
        response = self.client.post(self.unblock_user_url, {'blocked_user_id': self.user2.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('You have not blocked this user', response.data['error'])
        
        # Cannot unblock yourself
        response = self.client.post(self.unblock_user_url, {'blocked_user_id': self.user1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('You cannot unblock yourself.', response.data['error'])
        
    def test_block_list(self):
        BlockList.objects.create(blocker=self.user1, blocked=self.user2)
        BlockList.objects.create(blocker=self.user1, blocked=self.user3)
        BlockList.objects.create(blocker=self.user2, blocked=self.user1)
        BlockList.objects.create(blocker=self.user3, blocked=self.user2)
        self.authenticate(self.user1)
        
        response = self.client.get(self.block_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['results'][0]['email'], self.user2.email)
        self.assertEqual(response.data['results'][1]['email'], self.user3.email)
        
    def test_friend_list(self):
        FriendRequest.objects.create(from_user=self.user1, to_user=self.user2, status='accepted')
        FriendRequest.objects.create(from_user=self.user1, to_user=self.user3, status='accepted')
        FriendRequest.objects.create(from_user=self.user2, to_user=self.user3, status='accepted')
        self.authenticate(self.user1)
        
        response = self.client.get(self.friend_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['results'][0]['email'], self.user2.email)
        self.assertEqual(response.data['results'][1]['email'], self.user3.email)
        
    def test_pending_friend_requests(self):
        FriendRequest.objects.create(from_user=self.user1, to_user=self.user2, status='pending')
        FriendRequest.objects.create(from_user=self.user2, to_user=self.user3, status='pending')
        FriendRequest.objects.create(from_user=self.user3, to_user=self.user1, status='pending')
        
        self.authenticate(self.user2)
        
        response = self.client.get(self.pending_request_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['email'], self.user1.email)
        
    def test_throttling_friend_requests(self):
        self.authenticate(self.user1)
        
        for _ in range(3):
            self.client.post(self.send_request_url, {'to_user_id': self.user2.id})
        
        response = self.client.post(self.send_request_url, {'to_user_id': self.user3.id})
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)




