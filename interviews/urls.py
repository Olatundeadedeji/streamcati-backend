from django.urls import path
from . import views

urlpatterns = [
    path('', views.InterviewListCreateView.as_view(), name='interview-list-create'),
    path('<int:pk>/', views.InterviewRetrieveUpdateDestroyView.as_view(), name='interview-detail'),
    path('questions/', views.QuestionListView.as_view(), name='question-list'),
    path('response/', views.create_response, name='create-response'),
    path('contact/<int:contact_id>/rounds/', views.ContactInterviewRoundsView.as_view(), name='contact-interview-rounds'),
    path('contact/<int:contact_id>/round/<int:round_number>/start/', views.start_interview_round, name='start-interview-round'),
]
