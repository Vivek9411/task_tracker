import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from tracker.models import Goal, Task, Quiz, QuizQuestion
from tracker.serializers import QuizSerializer
from tracker.ai_helper import generate_quiz_questions

logger = logging.getLogger(__name__)

class GoalQuizGenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        tasks = goal.tasks.all()
        
        # Format task details for prompt context
        tasks_data = [
            {
                "title": t.title,
                "description": t.description
            }
            for t in tasks
        ]

        try:
            # Query LLM or fallback mock questions
            generated_questions = generate_quiz_questions(goal.title, tasks_data)
            
            # Create a new quiz instance
            quiz = Quiz.objects.create(goal=goal, user=request.user)
            
            # Create QuizQuestion records
            for q in generated_questions:
                QuizQuestion.objects.create(
                    quiz=quiz,
                    question_text=q["question_text"],
                    options=q["options"],
                    correct_option_index=q["correct_option_index"],
                    explanation=q["explanation"]
                )
                
            serializer = QuizSerializer(quiz)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Failed to generate quiz")
            return Response(
                {"error": f"Failed to generate quiz: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class QuizDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
        serializer = QuizSerializer(quiz)
        return Response(serializer.data)


class QuizSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
        
        if quiz.is_submitted:
            return Response(
                {"error": "This quiz has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        answers = request.data.get("answers", {})
        # Expecting format: { "question_id_1": 0, "question_id_2": 2, ... }
        
        questions = quiz.questions.all()
        correct_count = 0
        
        for q in questions:
            q_id_str = str(q.id)
            selected_option = answers.get(q_id_str)
            if selected_option is not None:
                try:
                    selected_idx = int(selected_option)
                    q.user_answer_index = selected_idx
                    if selected_idx == q.correct_option_index:
                        correct_count += 1
                except (ValueError, TypeError):
                    pass
            q.save()
            
        quiz.score = correct_count
        quiz.is_submitted = True
        quiz.save()
        
        serializer = QuizSerializer(quiz)
        return Response(serializer.data)
