from django.urls import path
from . import views

urlpatterns = [
    path('', views.ContactListCreateView.as_view(), name='contact-list-create'),
    path('<int:pk>/', views.ContactRetrieveUpdateDestroyView.as_view(), name='contact-detail'),
]