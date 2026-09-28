from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Streak, Goal, GoalQuestion, Task, ProgressLog, Quiz, QuizQuestion

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(' '.join(e.messages))
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user


class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = ['current_streak', 'longest_streak', 'last_activity_date']


class UserSerializer(serializers.ModelSerializer):
    streak = StreakSerializer(read_only=True)
    is_2fa_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'streak', 'is_2fa_enabled']

    def get_is_2fa_enabled(self, obj):
        profile = getattr(obj, 'profile', None)
        return bool(profile and profile.is_2fa_enabled)



class GoalQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalQuestion
        fields = ['id', 'question_text', 'answer_text', 'order']
        read_only_fields = ['id', 'question_text', 'order']


class GoalSerializer(serializers.ModelSerializer):
    questions = GoalQuestionSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Goal
        fields = ['id', 'user', 'title', 'experience_level', 'total_days', 'schedule_type', 'questions_answered', 'created_at', 'questions', 'is_ai', 'frequency_days_per_week', 'duration_weeks']
        read_only_fields = ['id', 'user', 'questions_answered', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'goal', 'title', 'description', 'scheduled_date', 'order_index', 'is_completed', 'completed_at', 'is_user_added']
        read_only_fields = ['id', 'goal', 'completed_at']


class ProgressLogSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = ProgressLog
        fields = ['id', 'goal', 'task', 'task_title', 'log_date', 'learned', 'problems_faced', 'additional_notes']
        read_only_fields = ['id', 'log_date']

    def validate(self, data):
        def get_val(field):
            if field in data:
                return data[field] or ''
            return getattr(self.instance, field, '') if self.instance else ''

        learned = str(get_val('learned')).strip()
        problems = str(get_val('problems_faced')).strip()
        notes = str(get_val('additional_notes')).strip()

        if not learned and not problems and not notes:
            raise serializers.ValidationError("At least one field (Updates, Problems, or Notes) must be provided.")
        return data

    def validate_task(self, value):
        # Verify the task belongs to the requesting user
        request = self.context.get('request')
        if request and value.goal.user != request.user:
            raise serializers.ValidationError("This task does not belong to you.")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)


class QuizQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizQuestion
        fields = ['id', 'question_text', 'options', 'user_answer_index', 'correct_option_index', 'explanation']
        read_only_fields = ['id', 'question_text', 'options']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Prevent cheating: do not expose the correct option or explanation before submission
        if not instance.quiz.is_submitted:
            rep.pop('correct_option_index', None)
            rep.pop('explanation', None)
        return rep


class QuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, read_only=True)
    goal_title = serializers.CharField(source='goal.title', read_only=True)

    class Meta:
        model = Quiz
        fields = ['id', 'goal', 'goal_title', 'user', 'created_at', 'score', 'is_submitted', 'questions']
        read_only_fields = ['id', 'goal', 'user', 'created_at', 'score', 'is_submitted']

