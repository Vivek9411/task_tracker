import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Streak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Streak: {self.current_streak} days"

    def record_activity(self, today=None):
        """
        Increments current streak if the last activity was yesterday.
        Maintains current streak if activity is today.
        Resets current streak to 1 if last activity is older than yesterday.
        Updates longest streak if current streak exceeds it.
        """
        if today is None:
            today = timezone.localdate()

        if self.last_activity_date is None:
            # First activity ever
            self.current_streak = 1
        else:
            delta = today - self.last_activity_date
            if delta.days == 1:
                # Consecutive day
                self.current_streak += 1
            elif delta.days > 1:
                # Streak broken
                self.current_streak = 1
            # If delta.days == 0 (same day), current_streak remains unchanged

        self.last_activity_date = today
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        self.save()


class Goal(models.Model):
    SCHEDULE_CHOICES = [
        ('ALL_DAYS', 'All Days'),
        ('WEEKENDS_ONLY', 'Weekends Only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=255, help_text="e.g., Learning React")
    experience_level = models.CharField(max_length=50, default='Beginner')
    total_days = models.IntegerField(default=14)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_CHOICES, default='ALL_DAYS')
    questions_answered = models.BooleanField(default=False)
    is_ai = models.BooleanField(default=True)
    frequency_days_per_week = models.IntegerField(default=7, null=True, blank=True)
    duration_weeks = models.IntegerField(default=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class GoalQuestion(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    answer_text = models.TextField(null=True, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order} for {self.goal.title}"


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    order_index = models.IntegerField(default=0)
    is_user_added = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order_index', 'scheduled_date']

    def __str__(self):
        return f"{self.title} - Completed: {self.is_completed}"

    def toggle_complete(self):
        """
        Toggles completion state and updates user streak if completed.
        """
        self.is_completed = not self.is_completed
        if self.is_completed:
            self.completed_at = timezone.now()
            # Record user streak activity
            streak, _ = Streak.objects.get_or_create(user=self.goal.user)
            streak.record_activity()
        else:
            self.completed_at = None
        self.save()


class ProgressLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='all_logs', null=True, blank=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress_logs')
    log_date = models.DateField(auto_now_add=True)
    learned = models.TextField(blank=True, help_text="What he learned")
    problems_faced = models.TextField(blank=True, help_text="Problems he faced")
    additional_notes = models.TextField(blank=True, help_text="Anything new he wants to add on")

    def __str__(self):
        title = self.task.title if self.task else self.goal.title if self.goal else "Unknown"
        return f"Log by {self.user.username} on {self.log_date} for {title}"


class Quiz(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='quizzes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(null=True, blank=True)
    is_submitted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Quiz for {self.goal.title} - Score: {self.score}"


class QuizQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    options = models.JSONField(help_text="List of 4 choices/options")
    correct_option_index = models.IntegerField(help_text="0-based index of correct option")
    explanation = models.TextField()
    user_answer_index = models.IntegerField(null=True, blank=True, help_text="0-based index of user selected option")

    def __str__(self):
        return f"Question in Quiz {self.quiz.id}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_2fa_enabled = models.BooleanField(default=False)
    google_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile (2FA: {self.is_2fa_enabled})"


class EmailOTP(models.Model):
    PURPOSE_CHOICES = [
        ('LOGIN_2FA', '2FA Login'),
        ('PASSWORDLESS', 'Passwordless Login'),
        ('PASSWORD_RESET', 'Password Reset'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps', null=True, blank=True)
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='PASSWORDLESS')
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.email} ({self.purpose}) - Used: {self.is_used}"

    def is_valid(self):
        return not self.is_used and timezone.now() <= self.expires_at


