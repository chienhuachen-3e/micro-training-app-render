from django import forms
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from django.forms import inlineformset_factory
from .models import Program, Topic, Lesson, Quiz, QuizChoice, QuizResponse, Enrollment, LessonProgress
from .forms import ProgramForm, TopicForm, LessonForm, QuizForm, QuizChoiceFormSet, EnrollmentManageForm, CourseSearchForm, QuizResponseForm, QuizGradingForm
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Exists, OuterRef
from django.db import IntegrityError

User = get_user_model()

class ManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_manager

# Program Views
class ProgramListView(LoginRequiredMixin, ListView):
    model = Program
    template_name = 'courses/program_list.html'
    context_object_name = 'programs'

    def get_queryset(self):
        if self.request.user.is_manager:
            # 管理员可以看到自己创建的所有课程
            return Program.objects.filter(created_by=self.request.user)
        else:
            # 普通用户可以看到所有课程（包括已加入和未加入的）
            return Program.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_manager:
            # 获取用户已加入的课程
            enrolled_programs = Program.objects.filter(enrolled_users=self.request.user)
            
            # 为每个课程添加未完成的测验信息
            for program in enrolled_programs:
                # 获取课程中所有的测验
                total_quizzes = Quiz.objects.filter(
                    lesson__topic__program=program
                ).count()
                
                # 获取用户已完成的测验
                completed_quizzes = QuizResponse.objects.filter(
                    quiz__lesson__topic__program=program,
                    user=self.request.user
                ).count()
                
                # 计算未完成的测验数量
                program.pending_quizzes = total_quizzes - completed_quizzes
            
            context['enrolled_programs'] = enrolled_programs
            context['available_programs'] = Program.objects.exclude(enrolled_users=self.request.user)
        return context

class ProgramDetailView(LoginRequiredMixin, DetailView):
    model = Program
    template_name = 'courses/program_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_manager'] = self.request.user.is_manager
        context['is_owner'] = self.object.created_by == self.request.user

        if self.request.user.is_manager:
            # 管理员视图直接使用原始数据
            context['topics'] = self.object.topics.all()
        else:
            # 学生视图使用处理后的数据
            processed_topics = []
            for topic in self.object.topics.all():
                processed_lessons = []
                for lesson in topic.lessons.all():
                    lesson_info = {
                        'lesson': lesson,
                        'has_quizzes': False,
                        'pending_quizzes': 0
                    }
                    
                    total_quizzes = lesson.quizzes.count()
                    if total_quizzes > 0:
                        lesson_info['has_quizzes'] = True
                        completed_quizzes = QuizResponse.objects.filter(
                            quiz__lesson=lesson,
                            user=self.request.user
                        ).count()
                        lesson_info['pending_quizzes'] = total_quizzes - completed_quizzes
                    
                    processed_lessons.append(lesson_info)
                
                topic_info = {
                    'topic': topic,
                    'lessons': processed_lessons
                }
                processed_topics.append(topic_info)
            
            context['processed_topics'] = processed_topics

        return context

class ProgramCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    model = Program
    form_class = ProgramForm
    template_name = 'courses/program_form.html'
    success_url = reverse_lazy('courses:program_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Program created successfully.')
        return super().form_valid(form)

class ProgramUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = Program
    form_class = ProgramForm
    template_name = 'courses/program_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('courses:program_detail', kwargs={'pk': self.object.pk})

class ProgramDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    model = Program
    template_name = 'courses/program_confirm_delete.html'
    success_url = reverse_lazy('courses:program_list')

    def dispatch(self, request, *args, **kwargs):
        program = self.get_object()
        if program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Program successfully deleted.')
        return super().delete(request, *args, **kwargs)

# Topic Views
class TopicCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    model = Topic
    form_class = TopicForm
    template_name = 'courses/topic_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.program = get_object_or_404(Program, pk=self.kwargs['program_id'])
        if self.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['program'] = self.program
        return context

    def form_valid(self, form):
        form.instance.program = self.program
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('courses:program_detail', kwargs={'pk': self.program.pk})

class TopicUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = Topic
    form_class = TopicForm
    template_name = 'courses/topic_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['program'] = self.object.program
        return context

    def get_success_url(self):
        return reverse('courses:program_detail', kwargs={'pk': self.object.program.pk})

class TopicDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    model = Topic
    template_name = 'courses/topic_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('courses:program_detail', kwargs={'pk': self.object.program.pk})

# Lesson Views
class LessonCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    model = Lesson
    form_class = LessonForm
    template_name = 'courses/lesson_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.topic = get_object_or_404(Topic, pk=self.kwargs['topic_id'])
        if self.topic.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topic'] = self.topic
        context['lesson'] = self.object if self.object else None
        return context

    def form_valid(self, form):
        form.instance.topic = self.topic
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('courses:program_detail', kwargs={'pk': self.topic.program.pk})

class LessonUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = Lesson
    form_class = LessonForm
    template_name = 'courses/lesson_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.topic.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topic'] = self.object.topic
        context['lesson'] = self.object
        return context

    def get_success_url(self):
        return reverse('courses:program_detail', kwargs={'pk': self.object.topic.program.pk})

class LessonDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    model = Lesson
    template_name = 'courses/lesson_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.topic.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('courses:program_detail', kwargs={'pk': self.object.topic.program.pk})

class QuizCreateView(LoginRequiredMixin, ManagerRequiredMixin, CreateView):
    model = Quiz
    form_class = QuizForm
    template_name = 'courses/quiz_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.lesson = get_object_or_404(Lesson, pk=self.kwargs['lesson_id'])
        if self.lesson.topic.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lesson'] = self.lesson
        if self.request.POST:
            context['choices_formset'] = QuizChoiceFormSet(self.request.POST)
        else:
            context['choices_formset'] = QuizChoiceFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        choices_formset = context['choices_formset']
        
        if form.instance.quiz_type == 'MCQ':
            if not choices_formset.is_valid():
                return self.form_invalid(form)
        
        self.object = form.save(commit=False)
        self.object.lesson = self.lesson
        self.object.save()
        
        if self.object.quiz_type == 'MCQ':
            choices_formset.instance = self.object
            choices_formset.save()
        
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('courses:lesson_detail', kwargs={'pk': self.lesson.pk})

class QuizUpdateView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = Quiz
    form_class = QuizForm
    template_name = 'courses/quiz_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.lesson.topic.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lesson'] = self.object.lesson
        return context

    def get_success_url(self):
        return reverse('courses:lesson_detail', kwargs={'pk': self.object.lesson.pk})

class QuizDeleteView(LoginRequiredMixin, ManagerRequiredMixin, DeleteView):
    model = Quiz
    template_name = 'courses/quiz_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.lesson.topic.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('courses:lesson_detail', kwargs={'pk': self.object.lesson.pk})

class QuizResponseListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    model = QuizResponse
    template_name = 'courses/quiz_responses.html'
    context_object_name = 'responses'

    def get_queryset(self):
        self.quiz = get_object_or_404(Quiz, pk=self.kwargs['quiz_id'])
        if self.quiz.created_by != self.request.user:
            return QuizResponse.objects.none()
        return QuizResponse.objects.filter(quiz=self.quiz)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['quiz'] = self.quiz
        return context

class GradeQuizResponseView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = QuizResponse
    fields = ['score']
    template_name = 'courses/grade_response.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.quiz.created_by != request.user:
            messages.error(request, "You don't have permission to grade this response.")
            return redirect('courses:program_detail', pk=self.object.quiz.lesson.topic.program.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.graded_by = self.request.user
        form.instance.graded_at = timezone.now()
        messages.success(self.request, 'Response graded successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('courses:quiz_responses', kwargs={'quiz_id': self.object.quiz.id})

class EnrollmentManageView(LoginRequiredMixin, ManagerRequiredMixin, View):
    template_name = 'courses/manage_enrollments.html'

    def get_program(self):
        program = get_object_or_404(Program, pk=self.kwargs['pk'])
        if program.created_by != self.request.user:
            raise PermissionDenied
        return program

    def get(self, request, *args, **kwargs):
        program = self.get_program()
        form = EnrollmentManageForm()
        enrolled_users = program.enrolled_users.all()
        
        context = {
            'program': program,
            'form': form,
            'enrolled_users': enrolled_users,
        }
        
        if request.headers.get('HX-Request'):
            users = form.filter_users(
                request.GET.get('search', ''),
                request.GET.get('department', '')
            ).exclude(id__in=enrolled_users.values_list('id', flat=True))
            context['users'] = users
            html = render_to_string(
                'courses/partials/user_list.html',
                context,
                request=request
            )
            return JsonResponse({'html': html})
            
        available_users = User.objects.filter(is_manager=False).exclude(
            id__in=enrolled_users.values_list('id', flat=True)
        )
        context['users'] = available_users
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        program = self.get_program()
        action = request.POST.get('action')
        user_ids = request.POST.getlist('users')
        
        # 准备基本上下文
        form = EnrollmentManageForm()
        enrolled_users = program.enrolled_users.all()
        available_users = User.objects.filter(is_manager=False).exclude(
            id__in=enrolled_users.values_list('id', flat=True)
        )
        
        context = {
            'program': program,
            'form': form,
            'enrolled_users': enrolled_users,
            'users': available_users
        }

        if not user_ids:
            messages.error(request, 'Please select at least one user.')
            return render(request, self.template_name, context)

        users = User.objects.filter(id__in=user_ids)

        if action == 'enroll':
            for user in users:
                enrollment, created = Enrollment.objects.get_or_create(
                    program=program,
                    user=user,
                    defaults={
                        'enrolled_by': request.user,
                    }
                )
            messages.success(request, f'Successfully enrolled {len(users)} users.')
        
        elif action == 'unenroll':
            if not user_ids:
                messages.error(request, 'Please select at least one user to unenroll.')
                return render(request, self.template_name, context)
            
            Enrollment.objects.filter(
                user__in=users,
                program=program
            ).delete()
            messages.success(request, f'Successfully unenrolled {len(users)} users.')

        # 更新已注册用户列表
        context['enrolled_users'] = program.enrolled_users.all()
        context['users'] = User.objects.filter(is_manager=False).exclude(
            id__in=context['enrolled_users'].values_list('id', flat=True)
        )
        
        return render(request, self.template_name, context)

@login_required
def enrollment_progress(request, pk):
    enrollment = get_object_or_404(Enrollment, pk=pk)
    
    # 检查权限：只有课程创建者或者被注册的用户可以查看
    if not (request.user == enrollment.program.created_by or request.user == enrollment.user):
        raise PermissionDenied
    
    context = {
        'enrollment': enrollment,
        'program': enrollment.program,
        'user': enrollment.user,
    }
    
    return render(request, 'courses/enrollment_progress.html', context)

class UserDashboardView(LoginRequiredMixin, ListView):
    model = Program
    template_name = 'courses/user_dashboard.html'
    context_object_name = 'all_courses'

    def get_queryset(self):
        queryset = Program.objects.all()
        form = CourseSearchForm(self.request.GET, 
                              creator_choices=User.objects.filter(is_manager=True))

        if form.is_valid():
            search = form.cleaned_data.get('search')
            creator = form.cleaned_data.get('creator')
            sort_by = form.cleaned_data.get('sort_by')
            progress = form.cleaned_data.get('progress')

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(created_by__username__icontains=search)
                )

            if creator:
                queryset = queryset.filter(created_by_id=creator)

            if sort_by == 'oldest':
                queryset = queryset.order_by('created_at')
            else:
                queryset = queryset.order_by('-created_at')

            if progress:
                enrollments = Enrollment.objects.filter(
                    user=self.request.user,
                    program=OuterRef('pk')
                )
                queryset = queryset.annotate(is_enrolled=Exists(enrollments))

                if progress == 'not_started':
                    queryset = queryset.filter(is_enrolled=False)
                elif progress == 'in_progress':
                    queryset = queryset.filter(
                        is_enrolled=True,
                        # Add logic for incomplete courses
                    )
                elif progress == 'completed':
                    queryset = queryset.filter(
                        is_enrolled=True,
                        # Add logic for completed courses
                    )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = CourseSearchForm(
            self.request.GET,
            creator_choices=User.objects.filter(is_manager=True)
        )
        context['enrolled_courses'] = Program.objects.filter(
            enrolled_users=self.request.user
        ).annotate(
            total_lessons=Count('topics__lessons'),
            completed_lessons=Count(
                'topics__lessons',
                filter=Q(topics__lessons__lessonprogress__user=self.request.user,
                        topics__lessons__lessonprogress__completed=True)
            )
        )
        return context

class LessonDetailView(LoginRequiredMixin, DetailView):
    model = Lesson
    template_name = 'courses/lesson_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_manager'] = self.request.user.is_manager
        context['is_owner'] = self.object.topic.program.created_by == self.request.user

        if not self.request.user.is_manager:
            # 获取所有测验
            all_quizzes = self.object.quizzes.all()
            user_responses = QuizResponse.objects.filter(
                quiz__in=all_quizzes,
                user=self.request.user
            ).select_related('quiz', 'selected_choice')
            
            # 创建已回答测验的ID集合
            answered_quiz_ids = set(response.quiz.id for response in user_responses)
            
            # 未完成的测验
            context['pending_quizzes'] = [
                quiz for quiz in all_quizzes 
                if quiz.id not in answered_quiz_ids
            ]
            
            # 已完成的测验响应
            completed_responses = user_responses.order_by('-submitted_at')
            
            # 分离待评分和已评分的测验
            context['waiting_for_grading'] = [
                response for response in completed_responses
                if (response.quiz.quiz_type == 'OPEN' and 
                    response.grading_status == 'PENDING')
            ]
            
            context['graded_responses'] = [
                response for response in completed_responses
                if (response.quiz.quiz_type == 'MCQ' or 
                    response.grading_status == 'GRADED')
            ]

        return context

    def get_next_lesson(self):
        current_topic_lessons = self.object.topic.lessons.order_by('order')
        try:
            return current_topic_lessons.filter(
                order__gt=self.object.order
            )[0]
        except IndexError:
            next_topic = self.object.topic.program.topics.filter(
                order__gt=self.object.topic.order
            ).first()
            if next_topic:
                return next_topic.lessons.order_by('order').first()
        return None

    def get_prev_lesson(self):
        current_topic_lessons = self.object.topic.lessons.order_by('-order')
        try:
            return current_topic_lessons.filter(
                order__lt=self.object.order
            )[0]
        except IndexError:
            prev_topic = self.object.topic.program.topics.filter(
                order__lt=self.object.topic.order
            ).last()
            if prev_topic:
                return prev_topic.lessons.order_by('-order').first()
        return None

class QuizResponseCreateView(LoginRequiredMixin, CreateView):
    model = QuizResponse
    template_name = 'courses/quiz_response_form.html'
    form_class = QuizResponseForm

    def dispatch(self, request, *args, **kwargs):
        # 在任何处理之前检查
        self.quiz = get_object_or_404(Quiz, pk=self.kwargs['quiz_id'])
        if QuizResponse.objects.filter(quiz=self.quiz, user=request.user).exists():
            messages.error(request, '您已经回答过这个测验了！')
            return redirect('courses:lesson_detail', pk=self.quiz.lesson.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['quiz'] = self.quiz
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['quiz'] = self.quiz
        context['lesson'] = self.quiz.lesson
        return context

    def form_valid(self, form):
        # 再次检查，以防并发提交
        if QuizResponse.objects.filter(quiz=self.quiz, user=self.request.user).exists():
            messages.error(self.request, '您已经回答过这个测验了！')
            return redirect('courses:lesson_detail', pk=self.quiz.lesson.pk)
        
        try:
            form.instance.quiz = self.quiz
            form.instance.user = self.request.user
            response = super().form_valid(form)
            messages.success(self.request, '测验答案提交成功！')
            return response
        except IntegrityError:
            messages.error(self.request, '提交失败，您可能已经回答过这个测验。')
            return redirect('courses:lesson_detail', pk=self.quiz.lesson.pk)

    def get_success_url(self):
        return reverse('courses:lesson_detail', kwargs={'pk': self.quiz.lesson.pk})

class QuizGradingView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = QuizResponse
    form_class = QuizGradingForm
    template_name = 'courses/quiz_grading_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.quiz.lesson.topic.program.created_by != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.grading_status = 'GRADED'
        form.instance.graded_at = timezone.now()
        form.instance.graded_by = self.request.user
        response = form.save()
        messages.success(self.request, 'Quiz response has been graded successfully.')
        return redirect('courses:lesson_detail', pk=response.quiz.lesson.pk)

class EnrollCourseView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        program = get_object_or_404(Program, pk=kwargs['pk'])
        enrollment, created = Enrollment.objects.get_or_create(
            program=program,
            user=request.user,
            defaults={
                'enrolled_by': request.user,
            }
        )
        messages.success(request, f'You have successfully enrolled in {program.title}')
        return redirect('courses:user_dashboard')

class UnenrollCourseView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        program = get_object_or_404(Program, pk=kwargs['pk'])
        Enrollment.objects.filter(
            user=request.user,
            program=program
        ).delete()
        messages.success(request, f'You have unenrolled from {program.title}')
        return redirect('courses:user_dashboard')

class CompleteLessonView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        lesson = get_object_or_404(Lesson, pk=kwargs['pk'])
        progress, created = LessonProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={'completed': True, 'completed_at': timezone.now()}
        )
        if not created:
            progress.completed = True
            progress.completed_at = timezone.now()
            progress.save()
        
        messages.success(request, 'Lesson marked as completed!')
        return redirect('courses:lesson_detail', pk=lesson.pk)

class QuizResponseGradeView(LoginRequiredMixin, ManagerRequiredMixin, UpdateView):
    model = QuizResponse
    fields = ['points_earned', 'grading_comment']
    template_name = 'courses/grade_response.html'  # 实际上不会使用这个模板

    def form_valid(self, form):
        response = form.save(commit=False)
        response.grading_status = 'GRADED'
        response.graded_at = timezone.now()
        response.graded_by = self.request.user
        response.save()
        
        messages.success(self.request, 'Response has been graded successfully.')
        return redirect('courses:lesson_detail', pk=response.quiz.lesson.pk)

    def form_invalid(self, form):
        messages.error(self.request, 'Error in grading the response.')
        return redirect('courses:lesson_detail', pk=self.object.quiz.lesson.pk)