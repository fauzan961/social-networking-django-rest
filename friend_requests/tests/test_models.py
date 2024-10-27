from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.contrib.auth import get_user_model
from ..models import FriendRequest, BlockList, RejectedFriendRequest

User = get_user_model()

class FriendRequestModelTest(TestCase):
    
    def setUp(self):
        self.user1 = User.objects.create_user(email='user1@example.com', password='password123')
        self.user2 = User.objects.create_user(email='user2@example.com', password='password123')
    
    def test_friend_request_creation(self):
        """Test if a friend request can be created between two users."""
        friend_request = FriendRequest.objects.create(from_user=self.user1, to_user=self.user2)
        self.assertEqual(friend_request.from_user, self.user1)
        self.assertEqual(friend_request.to_user, self.user2)
        self.assertEqual(friend_request.status, 'pending')
    
    def test_self_friend_request_validation(self):
        """Test that a user cannot send a friend request to themselves."""
        with self.assertRaises(ValidationError):
            FriendRequest.objects.create(from_user=self.user1, to_user=self.user1)
    
    def test_reverse_friend_request_validation(self):
        """Test that a reverse friend request raises a validation error."""
        FriendRequest.objects.create(from_user=self.user1, to_user=self.user2)
        with self.assertRaises(ValidationError):
            FriendRequest.objects.create(from_user=self.user2, to_user=self.user1)  

    def test_cache_invalidation_on_save(self):
        """Test that the cache is invalidated on saving a FriendRequest."""
        cache_key = f"friend_list_{self.user1.id}"
        cache.set(cache_key, ['some cached data'], timeout=60 * 10)
        
        # Ensure cache has been set
        self.assertIsNotNone(cache.get(cache_key))

        # Creating a friend request should trigger cache invalidation
        FriendRequest.objects.create(from_user=self.user1, to_user=self.user2)
        self.assertIsNone(cache.get(cache_key))

    def test_cache_invalidation_on_delete(self):
        """Test that the cache is invalidated on deleting a FriendRequest."""
        friend_request = FriendRequest.objects.create(from_user=self.user1, to_user=self.user2)
        cache_key = f"friend_list_{self.user1.id}"
        cache.set(cache_key, ['some cached data'], timeout=60 * 10)
        
        # Ensure cache has been set
        self.assertIsNotNone(cache.get(cache_key))
        
        # Deleting the friend request should trigger cache invalidation
        friend_request.delete()
        self.assertIsNone(cache.get(cache_key))
        
class BlockModelTest(TestCase):
    
    def setUp(self):
        self.user1 = User.objects.create_user(email='user1@example.com', password='password123')
        self.user2 = User.objects.create_user(email='user2@example.com', password='password123')

    def test_block_user_creation(self):
        """Test if a user can block other user."""
        block_entry = BlockList.objects.create(blocker=self.user1, blocked=self.user2)
        self.assertEqual(block_entry.blocker, self.user1)
        self.assertEqual(block_entry.blocked, self.user2)
        
    def test_block_self_validation(self):
        """Test if User cannot block self."""
        with self.assertRaises(ValidationError):
            BlockList.objects.create(blocker=self.user1, blocked=self.user1)
            
class RejectedFriendRequestModelTest(TestCase):
    
    def setUp(self):
        self.user1 = User.objects.create_user(email='user1@example.com', password='password123')
        self.user2 = User.objects.create_user(email='user2@example.com', password='password123')
        
    def test_reject_friend_creation(self):
        """Test if a user can reject a friend request."""
        rejected_friends = RejectedFriendRequest.objects.create(from_user=self.user1, to_user=self.user2)
        self.assertEqual(rejected_friends.from_user, self.user1)
        self.assertEqual(rejected_friends.to_user, self.user2)
        
    def test_reject_request_self_validation(self):
        """Test if User cannot reject self."""
        with self.assertRaises(ValidationError):
            RejectedFriendRequest.objects.create(from_user=self.user1, to_user=self.user1)
