from django.contrib import admin
from .models import Question, Interview, Response


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'type', 'stage', 'required', 'order']
    list_filter = ['type', 'stage', 'required']
    search_fields = ['text']
    ordering = ['stage', 'order']


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ['contact', 'interviewer', 'stage', 'status', 'started_at']
    list_filter = ['status', 'stage', 'started_at']
    search_fields = ['contact__name', 'interviewer__username']
    readonly_fields = ['started_at', 'updated_at']


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ['interview', 'question', 'completed_at']
    list_filter = ['completed_at', 'question__stage']
    search_fields = ['interview__contact__name', 'question__text']
    readonly_fields = ['completed_at', 'updated_at']