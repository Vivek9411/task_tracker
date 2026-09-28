import logging
import io
import re
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import F
from django.http import FileResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from tracker.models import Streak, Goal, GoalQuestion, Task
from tracker.serializers import GoalSerializer, GoalQuestionSerializer, TaskSerializer
from tracker.ai_helper import generate_clarifying_questions, generate_study_plan

logger = logging.getLogger(__name__)


# --- Goal API ---

class GoalListCreateView(APIView):
    def get(self, request):
        goals = Goal.objects.filter(user=request.user).order_by('-created_at')
        return Response(GoalSerializer(goals, many=True).data)

    def post(self, request):
        serializer = GoalSerializer(data=request.data)
        if serializer.is_valid():
            goal = serializer.save(user=request.user)
            
            if not goal.is_ai:
                # Bypasses AI questions entirely
                goal.questions_answered = True
                goal.save()
                
                # Automatically generate manual tasks
                frequency = goal.frequency_days_per_week or 7
                duration = goal.duration_weeks or 2
                
                today = timezone.localdate()
                order_index = 0
                for w in range(duration):
                    for d in range(frequency):
                        offset = w * 7 + int(d * 7 / frequency)
                        scheduled_date = today + timedelta(days=offset)
                        Task.objects.create(
                            goal=goal,
                            title=f"{goal.title}: Lesson {order_index + 1}",
                            description=f"Study and practice session {order_index + 1} for {goal.title}.",
                            scheduled_date=scheduled_date,
                            order_index=order_index
                        )
                        order_index += 1
            else:
                # Call AI to generate 3 questions
                try:
                    questions = generate_clarifying_questions(goal.title)
                    for index, q_text in enumerate(questions):
                        GoalQuestion.objects.create(
                            goal=goal,
                            question_text=q_text,
                            order=index
                        )
                except Exception as e:
                    logger.error(f"Error creating questions: {e}")
                    # Create default fallbacks if AI fails
                    default_questions = [
                        f"What is your target timeframe to complete: {goal.title}?",
                        "What is your experience level? (Beginner, Intermediate, Expert)",
                        "Do you have a specific project you want to build?"
                    ]
                    for index, q_text in enumerate(default_questions):
                        GoalQuestion.objects.create(
                            goal=goal,
                            question_text=q_text,
                            order=index
                        )
            
            # Fetch fresh object with nested questions
            return Response(GoalSerializer(goal).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- Goal Interview Questions View ---

class GoalQuestionsView(APIView):
    def get(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        questions = goal.questions.all()
        return Response(GoalQuestionSerializer(questions, many=True).data)

    def post(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        if goal.questions_answered:
            return Response({'error': 'Questions already answered and plan generated.'}, status=status.HTTP_400_BAD_REQUEST)
            
        answers_data = request.data.get('answers', []) # Expects [{'id': int, 'answer': str}]
        
        for ans in answers_data:
            q_id = ans.get('id')
            ans_text = ans.get('answer')
            if q_id:
                try:
                    question = goal.questions.get(id=q_id)
                    question.answer_text = ans_text
                    question.save()
                except GoalQuestion.DoesNotExist:
                    pass
                    
        # Check if all questions are now answered
        unanswered = goal.questions.filter(answer_text__isnull=True)
        if unanswered.exists():
            return Response({'error': 'Please answer all questions.', 'unanswered_count': unanswered.count()}, status=status.HTTP_400_BAD_REQUEST)

        # Generate custom plan using AI
        qa_list = [{'question': q.question_text, 'answer': q.answer_text} for q in goal.questions.all()]
        
        try:
            plan_tasks = generate_study_plan(goal.title, goal.schedule_type, goal.total_days, qa_list)
            
            # Calculate calendar schedule dates
            scheduled_dates = self._calculate_schedule_dates(goal.schedule_type, goal.total_days)
            
            for index, item in enumerate(plan_tasks):
                Task.objects.create(
                    goal=goal,
                    title=item.get('title', f"Task {index+1}"),
                    description=item.get('description', ''),
                    scheduled_date=scheduled_dates[index] if index < len(scheduled_dates) else None,
                    order_index=index
                )
                
            goal.questions_answered = True
            goal.save()
            return Response({'message': 'Plan generated successfully!', 'tasks_count': len(plan_tasks)})
            
        except Exception as e:
            logger.error(f"Failed to generate study roadmap: {e}")
            return Response({'error': 'Failed to generate study plan.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _calculate_schedule_dates(self, schedule_type, count):
        """
        Generates scheduled dates based on Daily vs Saturday/Sunday setting.
        """
        today = timezone.localdate()
        dates = []
        
        if schedule_type == 'WEEKENDS_ONLY':
            current_date = today
            # If today is Monday-Friday, find upcoming Saturday (weekday 5)
            # Mon = 0, Tue = 1, Wed = 2, Thu = 3, Fri = 4, Sat = 5, Sun = 6
            if current_date.weekday() < 5:
                days_until_saturday = 5 - current_date.weekday()
                current_date = current_date + timedelta(days=days_until_saturday)
                
            for _ in range(count):
                dates.append(current_date)
                if current_date.weekday() == 5: # Saturday -> move to Sunday
                    current_date = current_date + timedelta(days=1)
                else: # Sunday -> move to next Saturday
                    current_date = current_date + timedelta(days=6)
        else: # ALL_DAYS
            for i in range(count):
                dates.append(today + timedelta(days=i))
                
        return dates


# --- Tasks list API ---

class GoalTasksView(APIView):
    def get(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        tasks = goal.tasks.all().order_by(F('scheduled_date').asc(nulls_last=True), 'order_index')
        return Response(TaskSerializer(tasks, many=True).data)


# --- Task Completion API ---

class TaskCompleteView(APIView):
    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, goal__user=request.user)
        task.toggle_complete()
        
        # Get active streak info
        streak, _ = Streak.objects.get_or_create(user=request.user)
        
        return Response({
            'is_completed': task.is_completed,
            'completed_at': task.completed_at,
            'current_streak': streak.current_streak,
            'longest_streak': streak.longest_streak
        })


class TaskCreateView(APIView):
    def post(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        title = request.data.get('title')
        description = request.data.get('description', '')
        scheduled_date_str = request.data.get('scheduled_date')
        
        if not title:
            return Response({'error': 'Title is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        scheduled_date = None
        if scheduled_date_str:
            try:
                scheduled_date = timezone.datetime.strptime(scheduled_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid date format. Expected YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            scheduled_date = timezone.localdate()
            
        # Get the next order index
        last_task = goal.tasks.all().order_by('-order_index').first()
        order_index = (last_task.order_index + 1) if last_task else 0
        
        task = Task.objects.create(
            goal=goal,
            title=title,
            description=description,
            scheduled_date=scheduled_date,
            order_index=order_index,
            is_user_added=True
        )
        
        # If the plan was not fully initialized/no tasks, make sure questions_answered is True
        if not goal.questions_answered:
            goal.questions_answered = True
            goal.save()
            
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskUpdateView(APIView):
    def get(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, goal__user=request.user)
        return Response(TaskSerializer(task).data)

    def patch(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, goal__user=request.user)
        
        if 'title' in request.data:
            task.title = request.data.get('title')
        if 'description' in request.data:
            task.description = request.data.get('description', '')
            
        if 'scheduled_date' in request.data:
            scheduled_date_str = request.data.get('scheduled_date')
            if scheduled_date_str:
                try:
                    task.scheduled_date = timezone.datetime.strptime(scheduled_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response({'error': 'Invalid date format. Expected YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                task.scheduled_date = None
                
        task.save()
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    def delete(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, goal__user=request.user)
        task.delete()
        return Response({'message': 'Task deleted successfully.'}, status=status.HTTP_200_OK)


class GoalDetailView(APIView):
    def delete(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        goal.delete()
        return Response({'message': 'Goal deleted successfully.'}, status=status.HTTP_200_OK)


class GoalPDFExportView(APIView):
    def get(self, request, goal_id):
        goal = get_object_or_404(Goal, id=goal_id, user=request.user)
        
        # Create an in-memory buffer
        buffer = io.BytesIO()
        
        # Create a ReportLab SimpleDocTemplate
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )
        
        # Create story elements list
        story = []
        
        # Styles setup
        styles = getSampleStyleSheet()
        
        # Main Title Style (Goal Title)
        title_style = ParagraphStyle(
            'GoalTitleStyle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            spaceAfter=15,
            textColor=colors.HexColor('#0F172A')  # Slate 900
        )
        
        # Heading 2 (Task Title)
        task_title_style = ParagraphStyle(
            'TaskTitleStyle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=17,
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
            textColor=colors.HexColor('#0F766E')  # Teal 700
        )
        
        # Heading 3 (Description and Notes Labels)
        sub_label_style = ParagraphStyle(
            'SubLabelStyle',
            parent=styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
            textColor=colors.HexColor('#475569')  # Slate 600
        )
        
        # Body text (Content of description and notes)
        body_style = ParagraphStyle(
            'PDFBodyStyle',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=14,
            spaceAfter=10,
            textColor=colors.HexColor('#334155')  # Slate 700
        )
        
        # Notes text (Progress Logs)
        notes_style = ParagraphStyle(
            'PDFNotesStyle',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=9,
            leading=13.5,
            spaceAfter=6,
            textColor=colors.HexColor('#334155')
        )
        
        # Helper to format text with reportlab tags
        def clean_pdf_html(text):
            if not text:
                return ""
            # Escape standard XML characters
            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            # Restore tags we want to support
            text = text.replace('&lt;br/&gt;', '<br/>')
            # Replace markdown bold **text** with <b>text</b>
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            # Replace markdown code `code` with <font face="Courier" color="#0F766E"><b>\1</b></font>
            text = re.sub(r'`(.*?)`', r'<font face="Courier" color="#0F766E"><b>\1</b></font>', text)
            # Replace newlines with <br/>
            text = text.replace('\n', '<br/>')
            return text
            
        # Add Goal Title
        story.append(Paragraph(goal.title, title_style))
        story.append(Spacer(1, 10))
        
        # Fetch tasks in order
        tasks = goal.tasks.all().order_by(F('scheduled_date').asc(nulls_last=True), 'order_index')
        
        for task in tasks:
            story.append(Paragraph(task.title, task_title_style))
            
            # Check if description exists
            desc_text = task.description.strip() if task.description else ""
            if desc_text:
                story.append(Paragraph("Description", sub_label_style))
                story.append(Paragraph(clean_pdf_html(desc_text), body_style))
                
            # Check if progress logs/notes exist
            logs = task.logs.all().order_by('log_date')
            if logs.exists():
                story.append(Paragraph("Progress Notes", sub_label_style))
                for log in logs:
                    log_date_str = log.log_date.strftime('%b %d, %Y')
                    log_parts = []
                    if log.learned.strip():
                        log_parts.append(f"<b>Learned:</b> {log.learned.strip()}")
                    if log.problems_faced.strip():
                        log_parts.append(f"<b>Blockers:</b> {log.problems_faced.strip()}")
                    if log.additional_notes.strip():
                        log_parts.append(f"<b>Notes:</b> {log.additional_notes.strip()}")
                        
                    if log_parts:
                        log_content = f"<i>{log_date_str}</i><br/>" + "<br/>".join(log_parts)
                        story.append(Paragraph(clean_pdf_html(log_content), notes_style))
                        
            # Visual separator between tasks
            story.append(Spacer(1, 8))
            
        # Build the PDF document
        doc.build(story)
        
        # Rewind the buffer
        buffer.seek(0)
        
        # Return FileResponse
        response = FileResponse(buffer, as_attachment=True, filename=f"{goal.title.replace(' ', '_')}_roadmap.pdf")
        return response
