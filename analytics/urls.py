from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('manager/', views.ManagerDashboardView.as_view(), name='manager_dashboard'),
    path('user/', views.UserDashboardView.as_view(), name='user_dashboard'),
    path('manager/update/', views.update_dashboard, name='update_dashboard'),
]