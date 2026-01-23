from django.urls import path

from . import views

urlpatterns = [
    path("groups", views.create_group, name="control-create-group"),
    path("users", views.list_users, name="control-list-users"),
    path("roles", views.list_roles, name="control-list-roles"),
    path("groups/add-user", views.add_user_to_group, name="control-add-user-to-group"),
    path("groups/add-roles", views.add_roles_to_group, name="control-add-roles-to-group"),
    path("notifications", views.create_notification, name="control-notifications-create"),
    path("notifications/unread-count", views.unread_notifications_count, name="control-notifications-unread-count"),
]
