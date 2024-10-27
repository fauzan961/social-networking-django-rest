from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ValidationError

class FriendRequest(models.Model):
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_requests', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('accepted', 'Accepted')], default='pending')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f"{self.from_user.email} -> {self.to_user.email} ({self.status})"
    
    def clean(self):
        if self.from_user == self.to_user:
            raise ValidationError("You cannot send a friend request to yourself.")
        
        if FriendRequest.objects.filter(from_user=self.to_user, to_user=self.from_user).exists():
            raise ValidationError("A reverse friend request already exists.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
@receiver(post_save, sender=FriendRequest)
@receiver(post_delete, sender=FriendRequest)
def invalidate_friend_cache(sender, instance, **kwargs):
        cache.delete(f"friend_list_{instance.from_user.id}")
        cache.delete(f"friend_list_{instance.to_user.id}")
        cache.delete(f"req_list_{instance.to_user.id}")
        
class RejectedFriendRequest(models.Model):
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='rejected_sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='rejected_received_requests', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.from_user.email} -> {self.to_user.email}"
    
    def clean(self):
        if self.from_user == self.to_user:
            raise ValidationError("You cannot send a friend request to yourself.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
class BlockList(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL,related_name='blocked_users', on_delete=models.CASCADE)
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL,related_name='blocked_by',on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
        indexes = [
            models.Index(fields=['blocker', 'blocked']),
        ]

    def __str__(self):
        return f"{self.blocker.email} blocked {self.blocked.email}"

    def clean(self):
        if self.blocker == self.blocked:
            raise ValidationError("You cannot block yourself.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
@receiver(post_save, sender=BlockList)
@receiver(post_delete, sender=BlockList)
def invalidate_block_cache(sender, instance, **kwargs):
        cache.delete(f"block_list_{instance.blocker.id}")