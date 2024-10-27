from django.contrib import admin
from .models import CustomUser
from friend_requests.models import FriendRequest, RejectedFriendRequest, BlockList

class CustomUserAdmin(admin.ModelAdmin):
    model = CustomUser
    list_display = ('email', 'first_name', 'last_name', 'name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'name')}),
        ('Permissions', {'fields': ('is_staff', 'is_active')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'is_staff', 'is_active')}
        ),
    )
    ordering = ('email',)

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(FriendRequest)
admin.site.register(RejectedFriendRequest)
admin.site.register(BlockList)

