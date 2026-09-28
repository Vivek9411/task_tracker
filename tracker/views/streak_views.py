from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from tracker.models import Streak, Goal, Task
from tracker.serializers import StreakSerializer

class StreakView(APIView):
    def get(self, request):
        streak, _ = Streak.objects.get_or_create(user=request.user)
        return Response(StreakSerializer(streak).data)

class AnalyticsView(APIView):
    def get(self, request):
        user = request.user
        streak, _ = Streak.objects.get_or_create(user=user)
        
        active_goals = Goal.objects.filter(user=user).count()
        total_tasks_completed = Task.objects.filter(goal__user=user, is_completed=True).count()
        
        year_param = request.GET.get('year')
        
        if year_param and year_param.isdigit():
            year = int(year_param)
            completed_tasks = Task.objects.filter(
                goal__user=user,
                is_completed=True,
                completed_at__year=year
            )
        else:
            one_year_ago = timezone.now().date() - timedelta(days=365)
            completed_tasks = Task.objects.filter(
                goal__user=user, 
                is_completed=True,
                completed_at__date__gte=one_year_ago
            )
        
        heatmap_data = {}
        for task in completed_tasks:
            date_str = task.completed_at.date().isoformat()
            heatmap_data[date_str] = heatmap_data.get(date_str, 0) + 1
            
        return Response({
            'analytics': {
                'active_goals': active_goals,
                'total_completed': total_tasks_completed,
                'current_streak': streak.current_streak,
                'longest_streak': streak.longest_streak,
            },
            'heatmap_data': heatmap_data
        })
