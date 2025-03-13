from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Avg, Case, When, FloatField, Q
from django.db.models.functions import TruncMonth, TruncDate
from django.utils import timezone
from datetime import timedelta
from courses.models import Program, QuizResponse, Topic, Lesson, Enrollment, Quiz
from progress.models import ProgramEnrollment, LessonProgress
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from accounts.models import User
from django.contrib.auth.decorators import login_required

class UserAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/user_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 学习进度统计
        enrollments = ProgramEnrollment.objects.filter(user=user)
        context.update({
            'total_enrolled': enrollments.count(),
            'completed_programs': enrollments.filter(completed=True).count(),
            'in_progress_programs': enrollments.filter(completed=False).count(),
        })

        # 测验成绩统计
        quiz_stats = QuizResponse.objects.filter(
            quiz__lesson__topic__program__created_by=self.request.user
        ).aggregate(
            avg_score=Avg('points_earned'),
            total_attempts=Count('id')
        )
        
        context['quiz_stats'] = quiz_stats

        # 学习时间趋势
        last_30_days = timezone.now() - timedelta(days=30)
        daily_progress = LessonProgress.objects.filter(
            user=user,
            completed_at__gte=last_30_days
        ).annotate(
            date=TruncDate('completed_at')
        ).values('date').annotate(
            lessons_completed=Count('id')
        ).order_by('date')
        
        context['daily_progress'] = daily_progress

        return context

class ManagerAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'analytics/manager_dashboard.html'

    def test_func(self):
        return self.request.user.is_manager

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 平台总体统计
        context.update({
            'total_users': ProgramEnrollment.objects.values('user').distinct().count(),
            'total_programs': Program.objects.count(),
            'total_completions': ProgramEnrollment.objects.filter(completed=True).count(),
        })

        # 项目参与度分析
        program_analytics = Program.objects.annotate(
            enrolled_count=Count('programenrollment__user', distinct=True),
            completion_rate=Avg(
                Case(
                    When(programenrollment__completed=True, then=100),
                    default=0,
                    output_field=FloatField(),
                )
            ),
            avg_quiz_score=Avg('lesson__quiz__quizattempt__score')
        ).values('title', 'enrolled_count', 'completion_rate', 'avg_quiz_score')
        
        context['program_analytics'] = program_analytics

        # 部门学习情况
        department_analytics = ProgramEnrollment.objects.values(
            'user__department'
        ).annotate(
            user_count=Count('user', distinct=True),
            completion_rate=Avg(
                Case(
                    When(completed=True, then=100),
                    default=0,
                    output_field=FloatField(),
                )
            ),
            avg_quiz_score=Avg('user__quizattempt__score')
        )
        
        context['department_analytics'] = department_analytics

        return context

class ManagerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/manager_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_manager:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 获取所有可用的筛选选项
        context['programs'] = Program.objects.filter(created_by=self.request.user)
        context['departments'] = set(user.department for user in User.objects.all() if user.department)
        context['users'] = User.objects.filter(is_manager=False)
        
        # 获取基础统计数据
        context['active_programs_count'] = Program.objects.filter(
            created_by=self.request.user
        ).count()
        
        context['total_enrollments'] = Enrollment.objects.filter(
            program__created_by=self.request.user
        ).count()
        
        context['pending_grading_count'] = QuizResponse.objects.filter(
            quiz__lesson__topic__program__created_by=self.request.user,
            grading_status='pending'
        ).count()
        
        return context

    def get_filtered_data(self, request):
        """处理AJAX请求获取筛选后的数据"""
        programs = request.GET.getlist('programs[]')
        departments = request.GET.getlist('departments[]')
        users = request.GET.getlist('users[]')
        time_range = request.GET.get('timeRange')

        # 构建基础查询
        query = Program.objects.filter(created_by=request.user)
        
        # 应用筛选器
        if programs:
            query = query.filter(id__in=programs)
        if departments:
            query = query.filter(enrolled_users__department__in=departments)
        if users:
            query = query.filter(enrolled_users__id__in=users)
            
        # 处理时间范围
        if time_range == 'custom':
            date_from = request.GET.get('dateFrom')
            date_to = request.GET.get('dateTo')
            if date_from and date_to:
                query = query.filter(
                    created_at__gte=date_from,
                    created_at__lte=date_to
                )
        elif time_range != 'all':
            days = int(time_range)
            date_threshold = timezone.now() - timezone.timedelta(days=days)
            query = query.filter(created_at__gte=date_threshold)

        # 准备返回数据
        data = {
            'programs': [],
            'completion_rates': [],
            'quiz_scores': []
        }
        
        for program in query:
            data['programs'].append({
                'id': program.id,
                'title': program.title,
                'completion_rate': program.get_completion_rate(),
                'avg_quiz_score': program.get_average_quiz_score(),
                'enrolled_count': program.enrolled_users.count(),
                'topics': [{
                    'title': topic.title,
                    'completion_rate': topic.get_completion_rate(),
                    'lessons': [{
                        'title': lesson.title,
                        'completion_count': lesson.get_completion_count(),
                        'quiz_average': lesson.get_quiz_average()
                    } for lesson in topic.lessons.all()]
                } for topic in program.topics.all()]
            })
            
        return JsonResponse(data)

class UserDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/user_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 保持现有的enrolled_programs（用于显示数量）
        context['enrolled_programs'] = Program.objects.filter(
            enrolled_users=user
        )
        
        # 添加带进度信息的programs（用于显示进度条）
        enrolled_programs = context['enrolled_programs']
        programs_with_progress = []
        for program in enrolled_programs:
            total_quizzes = Quiz.objects.filter(
                lesson__topic__program=program
            ).count()
            
            completed_quizzes = QuizResponse.objects.filter(
                user=user,
                quiz__lesson__topic__program=program,
                grading_status='GRADED'
            ).count()
            
            program_data = {
                'title': program.title,
                'completion_rate': (completed_quizzes / total_quizzes * 100) if total_quizzes > 0 else 0,
                'completed_quizzes': completed_quizzes,
                'total_quizzes': total_quizzes
            }
            programs_with_progress.append(program_data)
        
        context['programs'] = programs_with_progress  # 添加到上下文
        
        # 保持其他现有的统计数据不变
        total_lessons = Lesson.objects.filter(
            topic__program__enrolled_users=user
        ).count()
        
        completed_lessons = LessonProgress.objects.filter(
            user=user,
            completed=True
        ).count()
        
        context['overall_progress'] = {
            'completed_lessons': completed_lessons,
            'total_lessons': total_lessons,
            'percentage': (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        }
        
        # 保持现有的测验统计
        graded_responses = QuizResponse.objects.filter(
            user=user,
            grading_status='GRADED',
            points_earned__isnull=False
        ).select_related('quiz')

        total_points_earned = sum(response.points_earned for response in graded_responses)
        total_possible_points = sum(response.quiz.points for response in graded_responses)
        
        context['quiz_stats'] = {
            'total_quizzes': Quiz.objects.filter(
                lesson__topic__program__enrolled_users=user
            ).count(),
            'completed_quizzes': QuizResponse.objects.filter(
                user=user
            ).count(),
            'pending_grading': QuizResponse.objects.filter(
                user=user,
                grading_status='PENDING'
            ).count(),
            'average_score': (total_points_earned / total_possible_points * 100) if total_possible_points > 0 else 0
        }
        
        context['recent_activities'] = get_recent_activities(user)
        
        return context

def get_recent_activities(user):
    recent_responses = QuizResponse.objects.filter(
        user=user
    ).select_related('quiz').order_by('-submitted_at')[:5]

    activities = []
    for response in recent_responses:
        activities.append({
            'type': 'quiz_submission',
            'timestamp': response.submitted_at,
            'quiz': response.quiz,
            'points_earned': response.points_earned,  # 直接使用 response 的分数
            'description': f'Submitted quiz: {response.quiz.title}'
        })
    
    # 如果还有其他类型的活动，在这里添加...

    return sorted(activities, key=lambda x: x['timestamp'], reverse=True)

@login_required
def update_dashboard(request):
    try:
        if not request.user.is_manager:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # 获取筛选参数
        programs = request.GET.getlist('programs[]', [])
        departments = request.GET.getlist('departments[]', [])
        users = request.GET.getlist('users[]', [])
        time_range = request.GET.get('timeRange', 'all')

        # 构建基础查询
        query = Program.objects.filter(created_by=request.user)
        
        # 应用筛选器
        if 'all' not in programs and programs:
            query = query.filter(id__in=programs)
        if 'all' not in departments and departments:
            query = query.filter(enrolled_users__department__in=departments)
        if 'all' not in users and users:
            query = query.filter(enrolled_users__id__in=users)
            
        # 处理时间范围
        if time_range == 'custom':
            date_from = request.GET.get('dateFrom')
            date_to = request.GET.get('dateTo')
            if date_from and date_to:
                query = query.filter(
                    created_at__gte=date_from,
                    created_at__lte=date_to
                )
        elif time_range != 'all':
            days = int(time_range)
            date_threshold = timezone.now() - timezone.timedelta(days=days)
            query = query.filter(created_at__gte=date_threshold)

        programs_data = []
        total_completion = 0
        program_count = 0

        for program in query.distinct():
            # 计算程序完成率
            total_quizzes = Quiz.objects.filter(
                lesson__topic__program=program
            ).count()
            
            completed_quizzes = QuizResponse.objects.filter(
                quiz__lesson__topic__program=program,
                grading_status='GRADED'
            ).count()
            
            completion_rate = (completed_quizzes / total_quizzes * 100) if total_quizzes > 0 else 0
            total_completion += completion_rate
            program_count += 1

            # 计算每个主题和课程的完成率
            topics_data = []
            for topic in program.topics.all():
                # 获取主题的测验数据
                topic_total_quizzes = Quiz.objects.filter(
                    lesson__topic=topic
                ).count()
                
                topic_completed_quizzes = QuizResponse.objects.filter(
                    quiz__lesson__topic=topic,
                    grading_status='GRADED'
                ).count()
                
                topic_completion_rate = (topic_completed_quizzes / topic_total_quizzes * 100) if topic_total_quizzes > 0 else 0
                
                # 获取每个课程的数据
                lessons_data = []
                for lesson in topic.lessons.all():
                    lesson_total_quizzes = Quiz.objects.filter(
                        lesson=lesson
                    ).count()
                    
                    lesson_completed_quizzes = QuizResponse.objects.filter(
                        quiz__lesson=lesson,
                        grading_status='GRADED'
                    ).count()
                    
                    lesson_completion_rate = (lesson_completed_quizzes / lesson_total_quizzes * 100) if lesson_total_quizzes > 0 else 0
                    
                    lessons_data.append({
                        'title': lesson.title,
                        'completion_rate': round(lesson_completion_rate, 1),
                        'total_quizzes': lesson_total_quizzes,
                        'completed_quizzes': lesson_completed_quizzes
                    })

                topics_data.append({
                    'title': topic.title,
                    'completion_rate': round(topic_completion_rate, 1),
                    'total_quizzes': topic_total_quizzes,
                    'completed_quizzes': topic_completed_quizzes,
                    'lessons': lessons_data  # 添加课程数据
                })

            # 计算平均测验分数
            graded_responses = QuizResponse.objects.filter(
                quiz__lesson__topic__program=program,
                grading_status='GRADED'
            )
            
            total_score = sum(response.points_earned or 0 for response in graded_responses)
            total_possible = sum(response.quiz.points for response in graded_responses)
            avg_quiz_score = (total_score / total_possible * 100) if total_possible > 0 else 0

            program_data = {
                'id': program.id,
                'title': program.title,
                'enrolled_count': program.enrolled_users.count(),
                'completion_rate': round(completion_rate, 1),
                'avg_quiz_score': round(avg_quiz_score, 1),
                'topics': topics_data
            }
            programs_data.append(program_data)

        data = {
            'active_programs_count': query.count(),
            'total_enrollments': Enrollment.objects.filter(
                program__in=query
            ).count(),
            'pending_grading_count': QuizResponse.objects.filter(
                quiz__lesson__topic__program__in=query,
                grading_status='PENDING'
            ).count(),
            'avg_completion_rate': round(total_completion / program_count, 1) if program_count > 0 else 0,
            'programs': programs_data
        }

        return JsonResponse(data)

    except Exception as e:
        print(f"Error in update_dashboard: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)