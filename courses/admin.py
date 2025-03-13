from django.contrib import admin
from .models import Program, Topic, Lesson

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ['title', 'description', 'created_at']
    search_fields = ['title']

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['title', 'program', 'order']
    list_filter = ['program']
    search_fields = ['title']

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'topic', 'order']
    list_filter = ['topic__program', 'topic']
    search_fields = ['title']