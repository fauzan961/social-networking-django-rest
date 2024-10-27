from django.urls import path
from .views import SendFriendRequestView, ConfirmFriendRequestView, \
BlockUserView, FriendListView, PendingRequestListView, UnblockUserView, \
BlockView

urlpatterns = [
    path('friend-request/', SendFriendRequestView.as_view(), name='send_friend_request'),
    path('friend-request/<int:friend_request_id>/', ConfirmFriendRequestView.as_view(), name='accept_friend_request'),
    path('block-user/', BlockUserView.as_view(), name='block_user'),
    path('unblock-user/', UnblockUserView.as_view(), name='unblock_user'),
    path('friend-list/', FriendListView.as_view(), name='friend_list'),
    path('request-list/', PendingRequestListView.as_view(), name='request_list'),
    path('block/', BlockView.as_view(), name='block_list'),
]
