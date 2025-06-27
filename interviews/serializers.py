from rest_framework import serializers
from .models import Interview, Question, Response, InterviewRound
from contacts.serializers import ContactSerializer


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id', 'text', 'type', 'stage', 'options', 'routing_logic',
            'required', 'order', 'round', 'created_at'
        ]


class InterviewRoundSerializer(serializers.ModelSerializer):
    can_start_interview = serializers.ReadOnlyField()
    
    class Meta:
        model = InterviewRound
        fields = [
            'id', 'round_number', 'status', 'scheduled_at', 
            'created_at', 'updated_at', 'can_start_interview'
        ]


class ResponseSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Response
        fields = ['id', 'question_id', 'answer', 'completed_at', 'updated_at']
        read_only_fields = ['id', 'completed_at', 'updated_at']

    def create(self, validated_data):
        question_id = validated_data.pop('question_id')
        question = Question.objects.get(id=question_id)
        validated_data['question'] = question
        validated_data['interview'] = self.context['interview']
        
        # Update or create response
        response, created = Response.objects.update_or_create(
            interview=validated_data['interview'],
            question=question,
            defaults={'answer': validated_data['answer']}
        )
        return response


class InterviewSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    contact_id = serializers.IntegerField()  # Remove write_only=True to make it readable
    interview_round_id = serializers.IntegerField(write_only=True, required=False)
    interview_round = InterviewRoundSerializer(read_only=True)
    responses = ResponseSerializer(many=True, read_only=True)
    
    class Meta:
        model = Interview
        fields = [
            'id', 'contact', 'contact_id', 'interview_round', 'interview_round_id',
            'stage', 'status', 'current_question_index', 'form_data', 'started_at',
            'completed_at', 'updated_at', 'responses'
        ]
        read_only_fields = ['id', 'started_at', 'updated_at']

    def validate(self, data):
        contact_id = data.get('contact_id')
        interview_round_id = data.get('interview_round_id')
        
        if contact_id and not interview_round_id:
            # If no round specified, get the current active round
            from contacts.models import Contact
            try:
                contact = Contact.objects.get(id=contact_id)
                current_round = contact.current_round
                if not current_round or not current_round.can_start_interview():
                    raise serializers.ValidationError(
                        "No active interview round available for this contact."
                    )
                data['interview_round_id'] = current_round.id
            except Contact.DoesNotExist:
                raise serializers.ValidationError("Contact not found.")
        
        return data

    def create(self, validated_data):
        validated_data['interviewer'] = self.context['request'].user
        
        # Get the interview round
        interview_round_id = validated_data.pop('interview_round_id')
        interview_round = InterviewRound.objects.get(id=interview_round_id)
        validated_data['interview_round'] = interview_round
        
        return super().create(validated_data)


class ContactInterviewRoundsSerializer(serializers.Serializer):
    """Serializer for getting all rounds for a contact"""
    contact_id = serializers.IntegerField()
    rounds = InterviewRoundSerializer(many=True, read_only=True)
    
    def to_representation(self, instance):
        from contacts.models import Contact
        contact = Contact.objects.get(id=instance['contact_id'])
        return {
            'contact_id': contact.id,
            'contact_name': contact.name,
            'rounds': InterviewRoundSerializer(contact.interview_rounds.all(), many=True).data
        }
