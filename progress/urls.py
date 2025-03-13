from django.urls import path
from . import views

urlpatterns = [
    path('enroll/<int:program_id>/', views.enroll_program, name='enroll_program'),
    path('complete/<int:lesson_id>/', views.complete_lesson, name='complete_lesson'),
    path('my-progress/', views.UserProgressListView.as_view(), name='user_progress'),
    path('all-progress/', views.ManagerProgressView.as_view(), name='manager_progress'),
]