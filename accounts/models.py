from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    is_manager = models.BooleanField(
        default=False,
        verbose_name='is_manager'
    )
    department = models.CharField(
        max_length=100,
        blank=True,  # 允许为空
        verbose_name='Department'
    )
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({'Manager' if self.is_manager else 'Common user'})"