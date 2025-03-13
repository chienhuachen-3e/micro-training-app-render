from django.utils import timezone
from django.db import models
from django.conf import settings

class Program(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='created_programs',
        null=True,
        blank=True
    )
    enrolled_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='Enrollment',
        related_name='enrolled_programs',
        through_fields=('program', 'user')
    )
    
    def get_completion_rate(self, user=None):
        """获取项目完成率"""
        lessons = Lesson.objects.filter(topic__program=self)
        total_lessons = lessons.count()
        if total_lessons == 0:
            return 0
        
        if user:
            completed = LessonProgress.objects.filter(
                user=user,
                lesson__topic__program=self,
                completed=True
            ).count()
            return (completed / total_lessons) * 100
        
        # 所有用户的平均完成率
        enrollments = self.enrolled_users.all()
        if not enrollments:
            return 0
        
        total_rate = 0
        for user in enrollments:
            completed = LessonProgress.objects.filter(
                user=user,
                lesson__topic__program=self,
                completed=True
            ).count()
            total_rate += (completed / total_lessons) * 100
        
        return total_rate / enrollments.count()

    def get_average_quiz_score(self, user=None):
        """获取项目的平均测验分数"""
        query = QuizResponse.objects.filter(
            quiz__lesson__topic__program=self,
            points_earned__isnull=False
        )
        
        if user:
            query = query.filter(user=user)
            
        scores = query.values_list('points_earned', 'quiz__points')
        if not scores:
            return 0
            
        total_earned = sum(earned for earned, _ in scores)
        total_possible = sum(possible for _, possible in scores)
        
        return (total_earned / total_possible * 100) if total_possible > 0 else 0

    def __str__(self):
        return self.title

class Topic(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    description = models.TextField()
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def get_completion_rate(self, user=None):
        """获取主题完成率"""
        lessons = self.lessons.all()
        total_lessons = lessons.count()
        if total_lessons == 0:
            return 0
            
        if user:
            completed = LessonProgress.objects.filter(
                user=user,
                lesson__topic=self,
                completed=True
            ).count()
            return (completed / total_lessons) * 100
            
        # 所有用户的平均完成率
        enrollments = self.program.enrolled_users.all()
        if not enrollments:
            return 0
            
        total_rate = 0
        for user in enrollments:
            completed = LessonProgress.objects.filter(
                user=user,
                lesson__topic=self,
                completed=True
            ).count()
            total_rate += (completed / total_lessons) * 100
            
        return total_rate / enrollments.count()

    def __str__(self):
        return self.title

class Lesson(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    content = models.TextField()
    video_url = models.URLField(blank=True, null=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']

    def get_completion_count(self):
        """获取完成此课程的用户数"""
        return LessonProgress.objects.filter(
            lesson=self,
            completed=True
        ).count()

    def get_quiz_average(self):
        """获取此课程测验的平均分数"""
        responses = QuizResponse.objects.filter(
            quiz__lesson=self,
            points_earned__isnull=False
        )
        if not responses:
            return 0
            
        scores = responses.values_list('points_earned', 'quiz__points')
        total_earned = sum(earned for earned, _ in scores)
        total_possible = sum(possible for _, possible in scores)
        
        return (total_earned / total_possible * 100) if total_possible > 0 else 0

    
    def __str__(self):
        return self.title

class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    enrolled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='enrollments_created'
    )

    class Meta:
        unique_together = ['user', 'program']

class Quiz(models.Model):
    QUIZ_TYPES = (
        ('MCQ', 'Multiple Choice'),
        ('OPEN', 'Open Question')
    )
    
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    question = models.TextField()
    quiz_type = models.CharField(max_length=4, choices=QUIZ_TYPES)
    points = models.PositiveIntegerField(
        help_text="Maximum points for this question",
        default=10
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.get_quiz_type_display()})"

class QuizChoice(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.choice_text} ({'Correct' if self.is_correct else 'Incorrect'})"

    class Meta:
        unique_together = ['quiz', 'choice_text']

class QuizResponse(models.Model):
    GRADING_STATUS = (
        ('PENDING', 'Pending Review'),
        ('GRADED', 'Graded')
    )
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(
        QuizChoice, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    text_response = models.TextField(null=True, blank=True)
    points_earned = models.PositiveIntegerField(null=True, blank=True)
    grading_status = models.CharField(
        max_length=8, 
        choices=GRADING_STATUS, 
        default='PENDING'
    )
    grading_comment = models.TextField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,
        null=True, 
        related_name='graded_responses'
    )

    def save(self, *args, **kwargs):
        # 如果是多选题，自动评分
        if self.quiz.quiz_type == 'MCQ' and self.selected_choice:
            self.points_earned = self.quiz.points if self.selected_choice.is_correct else 0
            self.grading_status = 'GRADED'
            self.graded_at = timezone.now()
            # 设置系统为评分者
            if not self.graded_by:
                # 获取第一个超级用户作为系统评分者
                from django.contrib.auth import get_user_model
                User = get_user_model()
                system_grader = User.objects.filter(is_superuser=True).first()
                self.graded_by = system_grader
            # 添加自动评分反馈
            self.grading_comment = '自动评分: ' + ('回答正确！' if self.selected_choice.is_correct else '回答错误。')
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Response by {self.user.username} for {self.quiz.title}"

    class Meta:
        unique_together = ['quiz', 'user']

class LessonProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='course_lesson_progress'
    )
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name='course_progress'
    )
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'lesson']