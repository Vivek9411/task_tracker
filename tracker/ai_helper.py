import os
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from tracker.prompt import (
    CLARIFYING_QUESTIONS_SYSTEM_PROMPT,
    CLARIFYING_QUESTIONS_USER_PROMPT,
    STUDY_PLAN_SYSTEM_PROMPT,
    STUDY_PLAN_USER_PROMPT,
    QUIZ_SYSTEM_PROMPT,
    QUIZ_USER_PROMPT
)

logger = logging.getLogger(__name__)

# --- Structured Output Schema using Pydantic ---

class ClarifyingQuestions(BaseModel):
    questions: List[str] = Field(
        ..., 
        description="Exactly 3 specific, highly relevant clarifying questions to help customize a learning plan."
    )

class TaskItem(BaseModel):
    title: str = Field(
        ..., 
        description="Title of the task (e.g., 'Day 1: ...' or 'Weekend 1 - Saturday: ...')"
    )
    core_concepts: List[str] = Field(
        ..., 
        description="Concise list of core concepts or topics to study."
    )
    practical_exercises: List[str] = Field(
        ..., 
        description="Concise list of specific practical exercises or tasks to build."
    )
    expected_outputs: List[str] = Field(
        ..., 
        description="Concise list of expected outputs or verification criteria."
    )

class StudyPlan(BaseModel):
    tasks: List[TaskItem] = Field(
        ..., 
        description="The chronological list of scheduled task items."
    )


class QuestionSchema(BaseModel):
    question_text: str = Field(
        ...,
        description="The multiple choice question text based on the learning topics."
    )
    options: List[str] = Field(
        ...,
        description="Exactly 4 distinct options/choices."
    )
    correct_option_index: int = Field(
        ...,
        description="The 0-based index of the correct option (0, 1, 2, or 3)."
    )
    explanation: str = Field(
        ...,
        description="A detailed explanation of why the correct option is right and the reasoning behind it."
    )


class QuizSchema(BaseModel):
    questions: List[QuestionSchema] = Field(
        ...,
        description="Exactly 10 multiple choice questions covering the study plan topics and tasks."
    )


def get_llm():
    """
    Initializes and returns the LangChain ChatModel based on the env configuration.
    Defaults to Gemini if configured, or OpenAI, or OpenRouter, or returns None if no keys are found.
    """
    provider = os.environ.get("AI_PROVIDER", "gemini").lower()
    logger.info(f'provider: {provider}')
    
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        logger.info(f'api_key: {api_key}')
        if not api_key:
            # Fallback to GEMINI_API_KEY in case user put their OpenRouter key there
            api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("OPENROUTER_API_KEY is not set. Falling back to Mock AI.")
            return None
        model_name = os.environ.get("AI_MODEL_NAME", "google/gemma-2-9b-it:free")
        try:
            print(f'model_name is {model_name}')
            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                temperature=0.7,
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter ChatOpenAI: {e}")
            return None

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY is not set. Falling back to Mock AI.")
            return None
        try:
            return ChatOpenAI(model="gpt-4o-mini", temperature=0.7, api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpenAI: {e}")
            return None
            
    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY/GOOGLE_API_KEY is not set. Falling back to Mock AI.")
            return None
        try:
            model_name = os.environ.get("GEMINI_MODEL_NAME", 'gemini-1.5-flash')
            return ChatGoogleGenerativeAI(model=model_name, temperature=0.7, google_api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize ChatGoogleGenerativeAI: {e}")
            return None
            
    else:
        logger.warning(f"Unknown or unspecified AI_PROVIDER: {provider}. Falling back to Mock AI.")
        return None


def generate_clarifying_questions(goal_title: str) -> List[str]:
    """
    Generates 3 highly specific clarifying questions based on the goal title.
    Returns a list of strings representing the questions.
    """
    llm = get_llm()
    if not llm:
        logger.info(f'llm is none - returning mock questions')
        return _generate_mock_questions(goal_title)
        
    # 1. Try native structured output first (for models supporting tool calling)
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", CLARIFYING_QUESTIONS_SYSTEM_PROMPT),
            ("user", CLARIFYING_QUESTIONS_USER_PROMPT)
        ])
        structured_llm = llm.with_structured_output(ClarifyingQuestions)
        logger.info('structured_llm: {structured_llm}')
        
        chain = prompt | structured_llm
        result = chain.invoke({"goal_title": goal_title})
        if result and hasattr(result, 'questions') and len(result.questions) >= 3:
            return result.questions[:3]
    except Exception as e:
        logger.warning(f"Native structured output failed, falling back to JSON parsing: {e}")

    # 2. Fallback to Prompt + JsonOutputParser (for models without native tool calling like some OpenRouter free models)
    try:
        from langchain_core.output_parsers import JsonOutputParser
        parser = JsonOutputParser(pydantic_object=ClarifyingQuestions)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", CLARIFYING_QUESTIONS_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("user", CLARIFYING_QUESTIONS_USER_PROMPT)
        ])
        
        chain = prompt | llm | parser
        result = chain.invoke({
            "goal_title": goal_title,
            "format_instructions": parser.get_format_instructions()
        })
        
        if result and "questions" in result:
            questions = result["questions"]
            if isinstance(questions, list) and len(questions) >= 3:
                return questions[:3]
        elif isinstance(result, list) and len(result) >= 3:
            return result[:3]
    except Exception as e:
        logger.error(f"Fallback JSON parsing failed for clarifying questions: {e}")
        
    return _generate_mock_questions(goal_title)


def generate_study_plan(goal_title: str, schedule_type: str, total_days: int, qa_list: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Generates a structured list of tasks/lessons based on user answers.
    qa_list is a list of dicts: [{'question': str, 'answer': str}]
    Returns a list of dicts representing tasks:
    [{'title': str, 'description': str}]
    """
    llm = get_llm()
    if not llm:
        logger.info(f'llm is none - returning mock plan ')
        return _generate_mock_plan(goal_title, schedule_type, total_days)
        
    qa_formatted = "\n".join([f"Question: {item['question']}\nAnswer: {item['answer']}" for item in qa_list])
    
    # 1. Try native structured output first
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", STUDY_PLAN_SYSTEM_PROMPT),
            ("user", STUDY_PLAN_USER_PROMPT)
        ])
        structured_llm = llm.with_structured_output(StudyPlan)
        logger.info('stuctured llm output is {stuctured_llm}')
        chain = prompt | structured_llm
        result = chain.invoke({
            "goal_title": goal_title,
            "total_days": total_days,
            "schedule_type": schedule_type,
            "qa_formatted": qa_formatted
        })
        
        if result and hasattr(result, 'tasks') and len(result.tasks) > 0:
            tasks_list = []
            for t in result.tasks:
                core_str = "\n".join([f"- {item.strip()}" for item in t.core_concepts if item.strip()])
                practical_str = "\n".join([f"- {item.strip()}" for item in t.practical_exercises if item.strip()])
                output_str = "\n".join([f"- {item.strip()}" for item in t.expected_outputs if item.strip()])
                
                desc = (
                    f"**Core Concept:**\n{core_str}\n\n"
                    f"**Practical Exercise:**\n{practical_str}\n\n"
                    f"**Expected Output:**\n{output_str}"
                )
                tasks_list.append({
                    "title": t.title,
                    "description": desc
                })
            return _pad_tasks(tasks_list, goal_title, schedule_type, total_days)
    except Exception as e:
        logger.warning(f"Native structured study plan failed, falling back to JSON parsing: {e}")
        
    # 2. Fallback to Prompt + JsonOutputParser
    try:
        from langchain_core.output_parsers import JsonOutputParser
        parser = JsonOutputParser(pydantic_object=StudyPlan)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", STUDY_PLAN_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("user", STUDY_PLAN_USER_PROMPT)
        ])
        
        chain = prompt | llm | parser
        result = chain.invoke({
            "goal_title": goal_title,
            "total_days": total_days,
            "schedule_type": schedule_type,
            "qa_formatted": qa_formatted,
            "format_instructions": parser.get_format_instructions()
        })
        
        tasks_list = []
        if isinstance(result, dict) and "tasks" in result:
            for t in result["tasks"]:
                if isinstance(t, dict):
                    cores = t.get("core_concepts", t.get("core_concept", []))
                    if isinstance(cores, str):
                        cores = [c.strip() for c in cores.split("-") if c.strip()]
                    elif not isinstance(cores, list):
                        cores = []
                        
                    practicals = t.get("practical_exercises", t.get("practical_exercise", []))
                    if isinstance(practicals, str):
                        practicals = [p.strip() for p in practicals.split("-") if p.strip()]
                    elif not isinstance(practicals, list):
                        practicals = []
                        
                    outputs = t.get("expected_outputs", t.get("expected_output", []))
                    if isinstance(outputs, str):
                        outputs = [o.strip() for o in outputs.split("-") if o.strip()]
                    elif not isinstance(outputs, list):
                        outputs = []
                        
                    core_str = "\n".join([f"- {item}" for item in cores])
                    practical_str = "\n".join([f"- {item}" for item in practicals])
                    output_str = "\n".join([f"- {item}" for item in outputs])
                    
                    desc = (
                        f"**Core Concept:**\n{core_str}\n\n"
                        f"**Practical Exercise:**\n{practical_str}\n\n"
                        f"**Expected Output:**\n{output_str}"
                    )
                    tasks_list.append({
                        "title": t.get("title", "Task"),
                        "description": desc
                    })
        elif isinstance(result, list):
            for t in result:
                if isinstance(t, dict):
                    cores = t.get("core_concepts", t.get("core_concept", []))
                    if isinstance(cores, str):
                        cores = [c.strip() for c in cores.split("-") if c.strip()]
                    elif not isinstance(cores, list):
                        cores = []
                        
                    practicals = t.get("practical_exercises", t.get("practical_exercise", []))
                    if isinstance(practicals, str):
                        practicals = [p.strip() for p in practicals.split("-") if p.strip()]
                    elif not isinstance(practicals, list):
                        practicals = []
                        
                    outputs = t.get("expected_outputs", t.get("expected_output", []))
                    if isinstance(outputs, str):
                        outputs = [o.strip() for o in outputs.split("-") if o.strip()]
                    elif not isinstance(outputs, list):
                        outputs = []
                        
                    core_str = "\n".join([f"- {item}" for item in cores])
                    practical_str = "\n".join([f"- {item}" for item in practicals])
                    output_str = "\n".join([f"- {item}" for item in outputs])
                    
                    desc = (
                        f"**Core Concept:**\n{core_str}\n\n"
                        f"**Practical Exercise:**\n{practical_str}\n\n"
                        f"**Expected Output:**\n{output_str}"
                    )
                    tasks_list.append({
                        "title": t.get("title", "Task"),
                        "description": desc
                    })
                    
        if len(tasks_list) > 0:
            return _pad_tasks(tasks_list, goal_title, schedule_type, total_days)
    except Exception as e:
        logger.error(f"Fallback study plan JSON parsing failed: {e}")
        
    return _generate_mock_plan(goal_title, schedule_type, total_days)


def _pad_tasks(tasks_list: List[Dict[str, Any]], goal_title: str, schedule_type: str, total_days: int) -> List[Dict[str, Any]]:
    if len(tasks_list) < total_days:
        logger.warning(f"Generated plan has {len(tasks_list)} tasks, but {total_days} were requested. Padding plan.")
        mock_fallback = _generate_mock_plan(goal_title, schedule_type, total_days)
        while len(tasks_list) < total_days:
            tasks_list.append(mock_fallback[len(tasks_list)])
    return tasks_list[:total_days]


# --- FALLBACK MOCK SERVICE DATA ---

def _generate_mock_questions(goal_title: str) -> List[str]:
    return [
        f"What is your current prerequisite knowledge or experience related to {goal_title}? (Beginner, Intermediate, Advanced)",
        f"Are there specific aspects, tools, or frameworks inside {goal_title} you want to master?",
        "What is your primary output goal? (e.g. Build a portfolio application, prepare for coding interviews, or learn the theory)"
    ]


def _generate_mock_plan(goal_title: str, schedule_type: str, total_days: int) -> List[Dict[str, Any]]:
    plan = []
    
    # Generic, high-quality subjects based on goal
    topics = [
        ("Core Fundamentals & Concept Mapping", ["Baseline terminology", "Overview documentation"], ["Set up local development environment", "Initialize repository"], ["Working dev environment", "Clean README file"]),
        ("Basic Syntax & Environment Setup", ["Variables", "Data types", "Basic script structure"], ["Write a hello-world script", "Run syntax exercises"], ["Console output from script"]),
        ("State Management & Dataflow", ["State scopes", "Data direction"], ["Create state component", "Handle inputs"], ["Updated variables rendered on screen"]),
        ("Component Design & Composition", ["Sub-modules", "Props passing"], ["Split code base into reusable parts", "Pass props to child"], ["Props rendered correctly in child UI"]),
        ("Side Effects & Network Layer", ["Fetch API", "Async handling", "Errors"], ["Fetch data from an external JSON API", "Render list of elements"], ["Loaded list items displayed in UI"]),
        ("Form Handlers & Custom Validation", ["Form states", "Validation rules"], ["Build user forms with validation", "Display error tooltips"], ["Form showing errors for invalid data"]),
        ("Deep Dive & Best Practices", ["Code conventions", "DRY principles"], ["Optimize and clean the code base", "Refactor loops"], ["Clean code base with no redundancy"]),
        ("Mid-way Practical Workshop Project", ["Integration of core fundamentals"], ["Build a complete task manager app", "Add state updates"], ["Fully functional local task tracker"]),
        ("Advanced Hookings & Global States", ["Context systems", "Auth states"], ["Implement global context for settings", "Add auth state"], ["Preserved state across components"]),
        ("Dynamic Routing & Sub-pages", ["SPA routing", "URL parameters"], ["Integrate router protocols", "Add multi-page links"], ["Navigation works without page reload"]),
        ("Visual Layout & Styled Components", ["Glassmorphism UI", "Styling tokens"], ["Apply visual styles to workspace", "Add hover animations"], ["Visually polished, premium interface"]),
        ("Performance Tuning & Diagnostics", ["Query optimization", "Memory profiling"], ["Profile memory usage", "Run performance audit"], ["Performance report showing high score"]),
        ("Final Capstone Portfolio Project", ["Full application design"], ["Build a complete capstone project", "Polishing final layout"], ["Live interactive portfolio project"]),
        ("Deployment & Continuous Operations", ["Compiling", "Production hosting"], ["Compile assets", "Deploy application"], ["Live app accessible via web URL"])
    ]

    for i in range(total_days):
        topic_idx = i % len(topics)
        title_val, cores, practicals, outputs = topics[topic_idx]
        
        # Calculate schedule titles based on weekend vs daily setting
        if schedule_type == 'WEEKENDS_ONLY':
            weekend_num = (i // 2) + 1
            day_name = "Saturday" if i % 2 == 0 else "Sunday"
            title = f"Weekend {weekend_num} - {day_name}: {title_val}"
        else:
            title = f"Day {i+1}: {title_val}"
            
        core_str = "\n".join([f"- {item}" for item in cores])
        practical_str = "\n".join([f"- {item}" for item in practicals])
        output_str = "\n".join([f"- {item}" for item in outputs])
        
        desc = (
            f"**Core Concept:**\n{core_str}\n\n"
            f"**Practical Exercise:**\n{practical_str}\n\n"
            f"**Expected Output:**\n{output_str}"
        )
        plan.append({
            'title': title,
            'description': desc
        })
        
    return plan


def generate_quiz_questions(goal_title: str, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generates exactly 10 multiple-choice questions with options, correct answers,
    and explanations based on the learning track's goal and tasks.
    Returns a list of dictionaries.
    """
    llm = get_llm()
    if not llm:
        logger.info("LLM is none - returning mock quiz questions")
        return _generate_mock_quiz(goal_title)

    tasks_formatted = "\n".join([
        f"- Task: {t.get('title')}\n  Description: {t.get('description')}"
        for t in tasks
    ])

    # 1. Try native structured output first
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", QUIZ_SYSTEM_PROMPT),
            ("user", QUIZ_USER_PROMPT)
        ])
        structured_llm = llm.with_structured_output(QuizSchema)
        chain = prompt | structured_llm
        result = chain.invoke({
            "goal_title": goal_title,
            "tasks_formatted": tasks_formatted
        })
        if result and hasattr(result, 'questions') and len(result.questions) == 10:
            return [
                {
                    "question_text": q.question_text,
                    "options": q.options,
                    "correct_option_index": q.correct_option_index,
                    "explanation": q.explanation
                }
                for q in result.questions
            ]
    except Exception as e:
        logger.warning(f"Native structured quiz generation failed, falling back to JSON parsing: {e}")

    # 2. Fallback to Prompt + JsonOutputParser
    try:
        from langchain_core.output_parsers import JsonOutputParser
        parser = JsonOutputParser(pydantic_object=QuizSchema)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", QUIZ_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("user", QUIZ_USER_PROMPT)
        ])
        
        chain = prompt | llm | parser
        result = chain.invoke({
            "goal_title": goal_title,
            "tasks_formatted": tasks_formatted,
            "format_instructions": parser.get_format_instructions()
        })
        
        questions_list = []
        if isinstance(result, dict) and "questions" in result:
            for q in result["questions"]:
                if isinstance(q, dict) and "question_text" in q and "options" in q:
                    questions_list.append({
                        "question_text": q.get("question_text"),
                        "options": q.get("options"),
                        "correct_option_index": int(q.get("correct_option_index", 0)),
                        "explanation": q.get("explanation", "")
                    })
        if len(questions_list) == 10:
            return questions_list
    except Exception as e:
        logger.error(f"Fallback quiz JSON parsing failed: {e}")

    return _generate_mock_quiz(goal_title)


def _generate_mock_quiz(goal_title: str) -> List[Dict[str, Any]]:
    # Create 10 dummy questions about the goal_title topic to act as a fallback
    questions = []
    topics = [
        ("Core Concepts", "What is the primary foundation of this field?"),
        ("Key Syntax & Setup", "Which setup configuration is commonly recommended first?"),
        ("State & Context", "How is internal state managed or propagated?"),
        ("Best Practices", "What is a major code quality recommendation here?"),
        ("Performance Tuning", "Which technique is best to optimize resource usage?"),
        ("Troubleshooting", "How should common errors/exceptions be addressed?"),
        ("Component Design", "What is the standard design pattern for composition?"),
        ("Deployment", "What is the best way to compile and host these files?"),
        ("Integration", "How do we connect this layer to external data APIs?"),
        ("Future-Proofing", "What is the most modern approach currently recommended?")
    ]
    for i, (subtopic, q_text) in enumerate(topics):
        questions.append({
            "question_text": f"[Assessment Q{i+1}] Regarding '{goal_title}' - {subtopic}: {q_text}",
            "options": [
                "The standard recommended pattern/practice.",
                "An outdated or legacy approach.",
                "A completely unrelated technique.",
                "None of the options listed."
            ],
            "correct_option_index": 0,
            "explanation": f"Understanding '{subtopic}' is essential. The first option represents the contemporary standard guidelines for '{goal_title}'."
        })
    return questions

