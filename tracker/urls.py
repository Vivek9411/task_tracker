from django.urls import path
from .views.auth_views import (
    RegisterView, LoginView, LogoutView, CurrentUserView,
    Verify2FALoginView, SendPasswordlessOTPView, VerifyPasswordlessOTPView,
    PasswordResetRequestView, PasswordResetConfirmView,
    GoogleAuthView, GoogleOAuthRedirectView, GoogleOAuthCallbackView,
    Toggle2FAView
)
from .views.streak_views import StreakView, AnalyticsView
from .views.task_views import (
    GoalListCreateView, GoalQuestionsView, GoalTasksView, 
    TaskCompleteView, TaskCreateView, TaskUpdateView, GoalPDFExportView,
    GoalDetailView
)
from .views.note_views import TaskLogsView, ProgressLogUpdateView, GoalLogsView
from .views.quiz_views import GoalQuizGenerateView, QuizDetailView, QuizSubmitView

urlpatterns = [
    # Auth endpoints
    path('auth/register/', RegisterView.as_view(), name='api-register'),
    path('auth/login/', LoginView.as_view(), name='api-login'),
    path('auth/login/verify-2fa/', Verify2FALoginView.as_view(), name='api-login-2fa'),
    path('auth/otp/send/', SendPasswordlessOTPView.as_view(), name='api-otp-send'),
    path('auth/otp/verify/', VerifyPasswordlessOTPView.as_view(), name='api-otp-verify'),
    path('auth/password-reset/send-otp/', PasswordResetRequestView.as_view(), name='api-password-reset-send'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='api-password-reset-confirm'),
    path('auth/google/', GoogleAuthView.as_view(), name='api-google-verify'),
    path('auth/google/login/', GoogleOAuthRedirectView.as_view(), name='api-google-login'),
    path('auth/google/callback/', GoogleOAuthCallbackView.as_view(), name='api-google-callback'),
    path('auth/user/2fa/toggle/', Toggle2FAView.as_view(), name='api-user-2fa-toggle'),
    path('auth/logout/', LogoutView.as_view(), name='api-logout'),
    path('auth/user/', CurrentUserView.as_view(), name='api-user'),


    # Streak endpoints
    path('user/streak/', StreakView.as_view(), name='api-streak'),
    path('user/analytics/', AnalyticsView.as_view(), name='api-analytics'),

    # Goal endpoints
    path('goals/', GoalListCreateView.as_view(), name='api-goals-list-create'),
    path('goals/<uuid:goal_id>/', GoalDetailView.as_view(), name='api-goal-detail'),
    path('goals/<uuid:goal_id>/questions/', GoalQuestionsView.as_view(), name='api-goal-questions'),
    path('goals/<uuid:goal_id>/tasks/', GoalTasksView.as_view(), name='api-goal-tasks'),
    path('goals/<uuid:goal_id>/tasks/create/', TaskCreateView.as_view(), name='api-task-create'),
    path('goals/<uuid:goal_id>/pdf/', GoalPDFExportView.as_view(), name='api-goal-pdf'),
    path('goals/<uuid:goal_id>/quiz/generate/', GoalQuizGenerateView.as_view(), name='api-quiz-generate'),

    # Quiz endpoints
    path('quizzes/<uuid:quiz_id>/', QuizDetailView.as_view(), name='api-quiz-detail'),
    path('quizzes/<uuid:quiz_id>/submit/', QuizSubmitView.as_view(), name='api-quiz-submit'),

    # Task & progress logging endpoints
    path('tasks/<uuid:task_id>/', TaskUpdateView.as_view(), name='api-task-update'),
    path('tasks/<uuid:task_id>/complete/', TaskCompleteView.as_view(), name='api-task-complete'),
    path('tasks/<uuid:task_id>/logs/', TaskLogsView.as_view(), name='api-task-logs'),
    path('goals/<uuid:goal_id>/logs/', GoalLogsView.as_view(), name='api-goal-logs'),
    path('logs/<uuid:log_id>/', ProgressLogUpdateView.as_view(), name='api-log-update'),
]


