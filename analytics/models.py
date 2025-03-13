from django.db import models
from django.conf import settings
from courses.models import Program

class LearningAnalytics(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    total_study_time = models.DurationField(default=0)  # 学习时长
    last_activity = models.DateTimeField(auto_now=True)  # 最后活动时间
    
    class Meta:
        unique_together = ['user', 'program']