from rest_framework import serializers
from .models import Contact


class ContactSerializer(serializers.ModelSerializer):
    interview_count = serializers.ReadOnlyField()
    current_round = serializers.SerializerMethodField()
    interview_rounds = serializers.SerializerMethodField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'name', 'phone', 'serialNumber', 'cuid', 'ticketNumber', 
            'location', 'status', 'notes', 'created_at', 'updated_at', 
            'last_contact', 'interview_count', 'current_round', 'interview_rounds'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'interview_count']

    def get_current_round(self, obj):
        current_round = obj.current_round
        if current_round:
            return {
                'id': current_round.id,
                'round_number': current_round.round_number,
                'status': current_round.status,
                'scheduled_at': current_round.scheduled_at,
                'can_start_interview': current_round.can_start_interview()
            }
        return None

    def get_interview_rounds(self, obj):
        rounds = obj.interview_rounds.all()
        return [{
            'id': round.id,
            'round_number': round.round_number,
            'status': round.status,
            'scheduled_at': round.scheduled_at,
            'can_start_interview': round.can_start_interview()
        } for round in rounds]

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
