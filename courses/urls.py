from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Program URLs
    path('', views.ProgramListView.as_view(), name='program_list'),
    path('program/new/', views.ProgramCreateView.as_view(), name='program_create'),
    path('program/<int:pk>/', views.ProgramDetailView.as_view(), name='program_detail'),
    path('program/<int:pk>/edit/', views.ProgramUpdateView.as_view(), name='program_update'),
    path('program/<int:pk>/delete/', views.ProgramDeleteView.as_view(), name='program_delete'),
    
    # Topic URLs
    path('program/<int:program_id>/topic/new/', views.TopicCreateView.as_view(), name='topic_create'),
    path('topic/<int:pk>/edit/', views.TopicUpdateView.as_view(), name='topic_update'),
    path('topic/<int:pk>/delete/', views.TopicDeleteView.as_view(), name='topic_delete'),
    
    # Lesson URLs
    path('topic/<int:topic_id>/lesson/new/', views.LessonCreateView.as_view(), name='lesson_create'),
    path('lesson/<int:pk>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lesson/<int:pk>/update/', views.LessonUpdateView.as_view(), name='lesson_update'),
    path('lesson/<int:pk>/delete/', views.LessonDeleteView.as_view(), name='lesson_delete'),

    # Quiz URLs
    path('lesson/<int:lesson_id>/quiz/new/', views.QuizCreateView.as_view(), name='quiz_create'),
    path('quiz/<int:pk>/update/', views.QuizUpdateView.as_view(), name='quiz_update'),
    path('quiz/<int:pk>/delete/', views.QuizDeleteView.as_view(), name='quiz_delete'),
    path('quiz/<int:quiz_id>/answer/', views.QuizResponseCreateView.as_view(), name='quiz_answer'),
    
    # Quiz Response URLs
    path('quiz-response/<int:pk>/grade/', views.QuizResponseGradeView.as_view(), name='grade_response'),
    path('quiz-responses/<int:quiz_id>/', views.QuizResponseListView.as_view(), name='quiz_responses'),

    # Enrollment management URLs
    path('program/<int:pk>/enrollments/', 
        views.EnrollmentManageView.as_view(), 
        name='manage_enrollments'),
    path('enrollment/<int:pk>/progress/',
        views.enrollment_progress,
        name='enrollment_progress'),

    # User course management URLs
    path('dashboard/', views.UserDashboardView.as_view(), name='user_dashboard'),
    path('lesson/<int:pk>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lesson/<int:pk>/complete/', views.CompleteLessonView.as_view(), name='complete_lesson'),
    path('course/<int:pk>/enroll/', views.EnrollCourseView.as_view(), name='enroll_course'),
    path('course/<int:pk>/unenroll/', views.UnenrollCourseView.as_view(), name='unenroll_course'),
]