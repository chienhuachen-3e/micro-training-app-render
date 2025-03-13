from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.utils import timezone
from .models import ProgramEnrollment, LessonProgress
from courses.models import Program, Lesson
from django.db.models import Count, Avg

@login_required
def enroll_program(request, program_id):
    program = get_object_or_404(Program, id=program_id)
    if not ProgramEnrollment.objects.filter(user=request.user, program=program).exists():
        ProgramEnrollment.objects.create(user=request.user, program=program)
        messages.success(request, f'您已成功加入 {program.title} 培训项目')
    return redirect('program_detail', pk=program_id)

@login_required
def complete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    progress, created = LessonProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson
    )
    if not progress.completed:
        progress.completed = True
        progress.completed_at = timezone.now()
        progress.save()
        messages.success(request, f'课程 {lesson.title} 已标记为完成！')
    return redirect('lesson_detail', pk=lesson_id)

class UserProgressListView(LoginRequiredMixin, ListView):
    model = ProgramEnrollment
    template_name = 'progress/user_progress.html'
    context_object_name = 'enrollments'

    def get_queryset(self):
        return ProgramEnrollment.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for enrollment in context['enrollments']:
            total_lessons = Lesson.objects.filter(
                topic__program=enrollment.program
            ).count()
            completed_lessons = LessonProgress.objects.filter(
                user=self.request.user,
                lesson__topic__program=enrollment.program,
                completed=True
            ).count()
            if total_lessons > 0:
                enrollment.progress_percentage = (completed_lessons / total_lessons) * 100
            else:
                enrollment.progress_percentage = 0
        return context

class ManagerProgressView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ProgramEnrollment
    template_name = 'progress/manager_progress.html'
    context_object_name = 'enrollments'

    def test_func(self):
        return self.request.user.is_manager

    def get_queryset(self):
        return ProgramEnrollment.objects.all().select_related('user', 'program')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollments = context['enrollments']
        for enrollment in enrollments:
            total_lessons = Lesson.objects.filter(
                topic__program=enrollment.program
            ).count()
            completed_lessons = LessonProgress.objects.filter(
                user=enrollment.user,
                lesson__topic__program=enrollment.program,
                completed=True
            ).count()
            if total_lessons > 0:
                enrollment.progress_percentage = (completed_lessons / total_lessons) * 100
            else:
                enrollment.progress_percentage = 0
        return context