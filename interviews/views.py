from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from .models import Interview, Question, Response as InterviewResponse, InterviewRound
from .serializers import (
    InterviewSerializer, QuestionSerializer, ResponseSerializer,
    InterviewRoundSerializer, ContactInterviewRoundsSerializer
)
from contacts.models import Contact


class InterviewListCreateView(generics.ListCreateAPIView):
    serializer_class = InterviewSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'stage']

    def get_queryset(self):
        return Interview.objects.filter(interviewer=self.request.user)


class InterviewRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InterviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Interview.objects.filter(interviewer=self.request.user)

    def perform_update(self, serializer):
        interview = serializer.save()
        # Update contact status when interview status changes
        if 'status' in serializer.validated_data:
            interview.contact.update_status_from_rounds()


class QuestionListView(generics.ListAPIView):
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['stage', 'type']

    def get_queryset(self):
        """
        Get questions based on round number if provided
        """
        queryset = Question.objects.all().order_by('stage', 'order')
        round_number = self.request.query_params.get('round', None)
        
        if round_number:
            # Filter questions that are either common (round=null) or specific to this round
            queryset = queryset.filter(
                models.Q(round__isnull=True) | models.Q(round=round_number)
            )
        
        return queryset


class ContactInterviewRoundsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contact_id):
        try:
            contact = Contact.objects.get(id=contact_id)
        except Contact.DoesNotExist:
            return Response(
                {'error': 'Contact not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Initialize rounds if they don't exist
        if not contact.interview_rounds.exists():
            contact.initialize_interview_rounds()

        serializer = ContactInterviewRoundsSerializer({
            'contact_id': contact_id,
            'rounds': contact.interview_rounds.all()
        })
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_response(request):
    interview_id = request.data.get('interview_id')
    
    try:
        interview = Interview.objects.get(
            id=interview_id,
            interviewer=request.user
        )
    except Interview.DoesNotExist:
        return Response(
            {'error': 'Interview not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    serializer = ResponseSerializer(
        data=request.data,
        context={'interview': interview}
    )
    
    if serializer.is_valid():
        response = serializer.save()
        return Response(ResponseSerializer(response).data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_interview_round(request, contact_id, round_number):
    try:
        contact = Contact.objects.get(id=contact_id)
        interview_round = contact.interview_rounds.get(round_number=round_number)
    except Contact.DoesNotExist:
        return Response(
            {'error': 'Contact not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except InterviewRound.DoesNotExist:
        return Response(
            {'error': 'Interview round not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not interview_round.can_start_interview():
        return Response(
            {
                'error': 'Cannot start interview for this round',
                'details': {
                    'status': interview_round.status,
                    'scheduled_at': interview_round.scheduled_at,
                    'can_start': interview_round.can_start_interview()
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if there's already an active interview for this round
    existing_interview = Interview.objects.filter(
        contact=contact,
        interview_round=interview_round,
        status__in=['in_progress', 'paused']
    ).first()

    if existing_interview:
        # Return the existing interview instead of creating a new one
        serializer = InterviewSerializer(existing_interview, context={'request': request})
        return Response(serializer.data)

    try:
        # Create new interview for this round
        interview = Interview.objects.create(
            contact=contact,
            interviewer=request.user,
            interview_round=interview_round,
            status='in_progress',
            stage=1,
            current_question_index=0
        )

        # Update interview round status to active
        interview_round.status = 'active'
        interview_round.save()

        serializer = InterviewSerializer(interview, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': f'Failed to create interview: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
