# System and User Prompt templates for LangChain AI helper

CLARIFYING_QUESTIONS_SYSTEM_PROMPT = (
    "You are a professional technical mentor. Your goal is to design a customized, structured study roadmap for a user."
)

CLARIFYING_QUESTIONS_USER_PROMPT = (
    "The user wants to start a learning track for: '{goal_title}'.\n\n"
    "Generate exactly 3 highly relevant and specific clarifying questions that will help you design a customized, structured, day-by-day study roadmap for this topic.\n\n"
    "Questions must inquire about:\n"
    "1. Their current prerequisite knowledge / experience level (e.g. JavaScript base when learning React).\n"
    "2. Specific subtopics or frameworks they are most interested in.\n"
    "3. Any secondary goals (e.g. building a portfolio project, preparing for an interview)."
)

STUDY_PLAN_SYSTEM_PROMPT = (
    "You are an elite study coordinator and AI mentor. You construct precise, structured, and customized study roadmaps."
)

STUDY_PLAN_USER_PROMPT = (
    "Create a highly structured learning plan for the goal: '{goal_title}'.\n\n"
    "Parameters:\n"
    "- Total Duration: {total_days} schedule increments (days or weekends).\n"
    "- Schedule Preference: {schedule_type} (either ALL_DAYS or WEEKENDS_ONLY).\n\n"
    "Additional Context from User Interview:\n"
    "{qa_formatted}\n\n"
    "Requirements:\n"
    "1. Generate exactly {total_days} lessons/tasks.\n"
    "2. If schedule is WEEKENDS_ONLY, label the task titles sequentially as 'Weekend 1 - Saturday: ...', 'Weekend 1 - Sunday: ...', 'Weekend 2 - Saturday: ...', etc.\n"
    "3. If schedule is ALL_DAYS, label them sequentially as 'Day 1: ...', 'Day 2: ...', etc.\n"
    "4. For each task, provide extremely concise, pointwise details for `core_concepts`, `practical_exercises`, and `expected_outputs` (each must be a list of brief string items; do not include theoretical explanations or long paragraphs).\n"
    "5. The plan must follow a logical learning progression from absolute basics to advanced topics."
)


QUIZ_SYSTEM_PROMPT = (
    "You are a professional educational assessment assistant. Your job is to create challenging, educational, multiple-choice quizzes to test a user's knowledge on a specific study track."
)

QUIZ_USER_PROMPT = (
    "Create a comprehensive quiz for the learning track: '{goal_title}'.\n\n"
    "Here are the study topics and tasks planned for this track:\n"
    "{tasks_formatted}\n\n"
    "Requirements:\n"
    "1. Generate exactly 10 multiple-choice questions.\n"
    "2. Each question must have exactly 4 options/choices.\n"
    "3. Provide the 0-based index of the correct option (0, 1, 2, or 3).\n"
    "4. Provide a detailed explanation of why the correct option is right and the reasoning behind it.\n"
    "5. Ensure the questions cover a mix of theoretical concepts and practical application scenarios from the topics list."
)

