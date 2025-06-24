from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from contacts.models import Contact

User = get_user_model()


class Question(models.Model):
    TYPE_CHOICES = [
        ('text', 'Text'),
        ('multiple_choice', 'Multiple Choice'),
        ('scale', 'Scale (1-10)'),
        ('boolean', 'Yes/No'),
    ]
    
    text = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    stage = models.IntegerField(default=1)
    options = models.JSONField(null=True, blank=True)  # For multiple choice questions
    routing_logic = models.JSONField(null=True, blank=True)  # For conditional routing
    required = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    round = models.IntegerField(null=True, blank=True, help_text="Interview round (1-4). Leave null for questions available in all rounds.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['stage', 'order']

    def __str__(self):
        round_info = f" (Round {self.round})" if self.round else " (All rounds)"
        return f"Stage {self.stage}: {self.text[:50]}...{round_info}"


class InterviewRound(models.Model):
    ROUND_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='interview_rounds')
    round_number = models.IntegerField(choices=[(1, 'Round 1'), (2, 'Round 2'), (3, 'Round 3'), (4, 'Round 4')])
    status = models.CharField(max_length=20, choices=ROUND_STATUS_CHOICES, default='pending')
    scheduled_at = models.DateTimeField(default=timezone.now)  # Added default
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['contact', 'round_number']
        ordering = ['contact', 'round_number']
    
    def __str__(self):
        return f"{self.contact.name} - Round {self.round_number} ({self.status})"
    
    @classmethod
    def calculate_next_round_date(cls, previous_date, months=3):
        """Calculate next round date 3 months later, excluding weekends"""
        # Add approximately 3 months (90 days)
        next_date = previous_date + timedelta(days=90)
        
        # Adjust for weekends - if it falls on weekend, move to next Monday
        while next_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            next_date += timedelta(days=1)
        
        return next_date
    
    @classmethod
    def create_rounds_for_contact(cls, contact):
        """Create all 4 rounds for a contact with proper scheduling"""
        if cls.objects.filter(contact=contact).exists():
            return  # Rounds already exist
        
        # Round 1 should always be active for new contacts or not_started status
        round1_date = timezone.now()
        round1_status = 'active'  # Always active for round 1
        
        # Calculate subsequent rounds (3 months apart, excluding weekends)
        round2_date = cls.calculate_next_round_date(round1_date)
        round3_date = cls.calculate_next_round_date(round2_date)
        round4_date = cls.calculate_next_round_date(round3_date)
        
        rounds_data = [
            (1, round1_date, round1_status),
            (2, round2_date, 'pending'),
            (3, round3_date, 'pending'),
            (4, round4_date, 'pending'),
        ]
        
        for round_num, scheduled_date, status in rounds_data:
            cls.objects.create(
                contact=contact,
                round_number=round_num,
                scheduled_at=scheduled_date,
                status=status
            )
    
    def can_start_interview(self):
        """Check if this round can start an interview"""
        # Round 1 can always start if not completed
        if self.round_number == 1:
            return self.status != 'completed'
        
        # Other rounds need to be active and scheduled time reached
        return (
            self.status == 'active' and 
            timezone.now() >= self.scheduled_at
        )
    
    def activate_if_ready(self):
        """Activate this round if it's time and previous rounds are completed"""
        if self.status != 'pending':
            return False
        
        # Check if it's time for this round
        if timezone.now() < self.scheduled_at:
            return False
        
        # Check if previous rounds are completed (except for round 1)
        if self.round_number > 1:
            previous_rounds = InterviewRound.objects.filter(
                contact=self.contact,
                round_number__lt=self.round_number
            )
            if not all(r.status == 'completed' for r in previous_rounds):
                return False
        
        self.status = 'active'
        self.save()
        return True


class Interview(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
    ]
    
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='interviews')
    interviewer = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='interviews',
        limit_choices_to={'role__in': ['interviewer', 'admin']}  # Only interviewers and admins can conduct interviews
    )
    interview_round = models.ForeignKey(
        InterviewRound, 
        on_delete=models.CASCADE, 
        related_name='interviews',
        null=True,  # Allow null for existing records
        default=None  # Default to None for existing records
    )
    stage = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    current_question_index = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-started_at']

    def clean(self):
        """Validate that interview can be created or resumed for this round"""
        if not self.pk:  # Only validate for new interviews
            if self.interview_round and not self.interview_round.can_start_interview():
                # Check if there's an existing interview that can be resumed
                existing_interview = Interview.objects.filter(
                    contact=self.contact,
                    interview_round=self.interview_round,
                    status__in=['in_progress', 'paused']
                ).first()
                
                if not existing_interview:
                    raise ValidationError(
                        f"Cannot start interview for {self.interview_round}. "
                        f"Round status: {self.interview_round.status}, "
                        f"Scheduled: {self.interview_round.scheduled_at}"
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # If interview is completed, mark the round as completed
        if self.status == 'completed' and self.interview_round and self.interview_round.status == 'active':
            self.interview_round.status = 'completed'
            self.interview_round.save()
            
            # Activate next round if it exists
            next_round = InterviewRound.objects.filter(
                contact=self.contact,
                round_number=self.interview_round.round_number + 1
            ).first()
            if next_round:
                next_round.activate_if_ready()

    def __str__(self):
        round_info = f"Round {self.interview_round.round_number}" if self.interview_round else "No Round"
        return f"Interview: {self.contact.name} - {round_info} - {self.status}"


class Response(models.Model):
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.JSONField()  # Flexible storage for different answer types
    completed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['interview', 'question']
        ordering = ['completed_at']

    def __str__(self):
        return f"Response: {self.interview.contact.name} - Q{self.question.id}"
