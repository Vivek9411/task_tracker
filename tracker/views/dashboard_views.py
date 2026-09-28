from django.conf import settings
from django.views.generic import TemplateView

class LoginPageView(TemplateView):
    template_name = "login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['google_client_id'] = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
        return context


class DashboardPageView(TemplateView):
    template_name = "dashboard.html"

class AnalyticsPageView(TemplateView):
    template_name = "analytics.html"

class TaskNotesPageView(TemplateView):
    template_name = "goal_notes.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['goal_id'] = self.kwargs.get('goal_id')
        return context


class QuizPageView(TemplateView):
    template_name = "quiz.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['goal_id'] = self.kwargs.get('goal_id')
        context['quiz_id'] = self.kwargs.get('quiz_id')
        return context

