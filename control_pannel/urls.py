from django.urls import path

from . import views

urlpatterns = [
    path("test-ws", views.test_websocket_message, name="control-test-ws"),
    path("groups", views.create_group, name="control-create-group"),
    path("users", views.list_users, name="control-list-users"),
    path("roles", views.list_roles, name="control-list-roles"),
    path("users/by-roles", views.list_users_by_roles, name="control-users-by-roles"),
    path("groups/add-user", views.add_user_to_group, name="control-add-user-to-group"),
    path("groups/add-roles", views.add_roles_to_group, name="control-add-roles-to-group"),
    path("notifications", views.create_notification, name="control-notifications-create"),
    path("notifications/me", views.get_notifications, name="control-notifications-me"),
]
