from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Contact(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('round_1', 'Round 1'),
        ('round_2', 'Round 2'),
        ('round_3', 'Round 3'),
        ('round_4', 'Round 4'),
        ('completed', 'Completed'),
        # Keep old choices for backward compatibility
        ('not started', 'Not started'),
        ('1', 'Round 1'),
        ('2', 'Round 2'),
        ('3', 'Round 3'),
        ('4', 'Round 4'),
    ]
    
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    serialNumber = models.CharField(max_length=100, blank=True, null=True)
    cuid = models.CharField(max_length=100, blank=True, null=True)
    ticketNumber = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contacts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contact = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['phone', 'serialNumber', 'cuid', 'ticketNumber']

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def interview_count(self):
        return self.interviews.count()

    @property
    def current_round(self):
        """Get the current active or pending interview round"""
        return self.interview_rounds.exclude(status='completed').order_by('round_number').first()

    def initialize_interview_rounds(self):
        """Initialize the 4 interview rounds for this contact"""
        from interviews.models import InterviewRound
        InterviewRound.create_rounds_for_contact(self)

    def update_status_from_rounds(self):
        """Update contact status based on interview rounds"""
        current_round = self.current_round
        
        if not current_round:
            # If no rounds exist or all rounds are completed
            completed_rounds = self.interview_rounds.filter(status='completed').count()
            if completed_rounds == 4:
                self.status = 'completed'
            elif completed_rounds == 0:
                self.status = 'not_started'
        else:
            # Set status based on current round
            self.status = f'round_{current_round.round_number}'
        
        self.save()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Normalize old status values to new format
        if self.status == 'not started':
            self.status = 'not_started'
        elif self.status in ['1', '2', '3', '4']:
            self.status = f'round_{self.status}'
        
        super().save(*args, **kwargs)
        
        if is_new:
            # Initialize interview rounds for new contacts
            self.initialize_interview_rounds()
