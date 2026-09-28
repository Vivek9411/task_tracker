from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from tracker.models import Task, ProgressLog
from tracker.serializers import ProgressLogSerializer

class TaskLogsView(APIView):
    def get(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, goal__user=request.user)
        logs = task.logs.all().order_by('log_date')
        return Response(ProgressLogSerializer(logs, many=True).data)

    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, goal__user=request.user)
        
        # We inject the task in request data
        data = request.data.copy()
        data['task'] = task.id
        
        serializer = ProgressLogSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProgressLogUpdateView(APIView):
    def patch(self, request, log_id):
        log = get_object_or_404(ProgressLog, id=log_id, user=request.user)
        
        serializer = ProgressLogSerializer(log, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
from django.db.models import Q

class GoalLogsView(APIView):
    def get(self, request, goal_id):
        # We fetch all logs that either directly belong to this Goal,
        # OR belong to a Task that belongs to this Goal.
        logs = ProgressLog.objects.filter(
            Q(goal_id=goal_id, user=request.user) | Q(task__goal_id=goal_id, user=request.user)
        ).order_by('log_date')
        return Response(ProgressLogSerializer(logs, many=True).data)

    def post(self, request, goal_id):
        from tracker.models import Goal
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        
        data = request.data.copy()
        data['goal'] = goal.id
        
        serializer = ProgressLogSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
