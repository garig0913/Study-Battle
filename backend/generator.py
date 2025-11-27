import os
import json
import uuid
import aiohttp
import logging
from typing import List, Dict, Optional
from models import GeneratedQuestion, VerificationResult, SourceChunk, QuestionType, Difficulty

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

GENERATE_PROBLEM_PROMPT = """You are a math/CS exam writer. ONLY use the provided context. DO NOT hallucinate outside it. Create ONE problem that is NEW but closely based on the examples and facts in the context. The problem must be solvable with the context.

Output JSON ONLY with these exact keys (no markdown, no code blocks, just raw JSON):
{{
  "question_id": "<uuid>",
  "question_text": "...",
  "question_type": "mcq|short|calc|code",
  "options": ["A ...", "B ..."] OR null,
  "correct_answer": "...",
  "solution_steps": "...",
  "source_chunks": [{{"file_name":"", "page":1, "chunk_id": "...", "char_range":"start-end"}}]
}}

Requirements:
- question_type must be one of: {question_types}
- difficulty level: {difficulty}
- For MCQ: provide exactly 4 options (A, B, C, D)
- For short/calc/code: options should be null
- correct_answer must be the exact expected answer
- solution_steps must show step-by-step how to get the answer
- source_chunks must reference the actual chunks used

Context:
{context}
"""

VERIFY_ANSWER_PROMPT = """You are an objective grader. Use ONLY the context below and the official solution. Evaluate the student's submitted answer.

Return JSON ONLY (no markdown, no code blocks):
{{
  "correct": true|false,
  "confidence": 0.0-1.0,
  "explanation": "...",
  "citation": [{{"file_name":"", "page":1, "chunk_id":"..."}}]
}}

Context:
{context}

Official Solution: {solution}
Correct Answer: {correct_answer}

Student Answer: {student_answer}

Grading rules:
- For MCQ: exact letter match required (A, B, C, or D)
- For short answers: semantic equivalence is acceptable
- For calc: numerical answer must match (allow small rounding differences)
- For code: logic must be correct, syntax variations acceptable
"""


class DeepSeekGenerator:
    
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.model = "deepseek-chat"
        self._session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _call_deepseek(self, prompt: str, max_retries: int = 2) -> Optional[str]:
        if not self.api_key:
            logger.warning("No DeepSeek API key found")
            return None
        
        session = await self._get_session()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"}
        }
        
        for attempt in range(max_retries):
            try:
                async with session.post(
                    DEEPSEEK_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error {response.status}: {error_text}")
            except Exception as e:
                logger.error(f"DeepSeek request failed (attempt {attempt + 1}): {e}")
        
        return None
    
    def _format_context(self, chunks: List[Dict]) -> str:
        context_parts = []
        for i, chunk in enumerate(chunks):
            chunk_info = f"[CHUNK {i+1}]\n"
            chunk_info += f"File: {chunk.get('file_name', 'unknown')}\n"
            chunk_info += f"Page: {chunk.get('page_number', chunk.get('page', 1))}\n"
            chunk_info += f"Chunk ID: {chunk.get('chunk_id', 'unknown')}\n"
            chunk_info += f"Content: {chunk.get('text', '')}\n"
            context_parts.append(chunk_info)
        return "\n---\n".join(context_parts)
    
    async def generate_question(
        self,
        chunks: List[Dict],
        question_types: List[QuestionType],
        difficulty: Difficulty,
        topic: Optional[str] = None
    ) -> Optional[GeneratedQuestion]:
        if not chunks:
            logger.warning("No chunks provided for question generation")
            return self._generate_fallback_question(chunks, question_types, difficulty)
        
        context = self._format_context(chunks)
        types_str = ", ".join([qt.value for qt in question_types])
        
        prompt = GENERATE_PROBLEM_PROMPT.format(
            question_types=types_str,
            difficulty=difficulty.value,
            context=context
        )
        
        response = await self._call_deepseek(prompt)
        
        if response:
            try:
                data = json.loads(response)
                
                source_chunks = []
                for sc in data.get("source_chunks", []):
                    source_chunks.append(SourceChunk(
                        doc_id=sc.get("doc_id", ""),
                        file_name=sc.get("file_name", ""),
                        page=sc.get("page", 1),
                        chunk_id=sc.get("chunk_id", ""),
                        char_start=0,
                        char_end=0
                    ))
                
                if not source_chunks and chunks:
                    for chunk in chunks[:2]:
                        source_chunks.append(SourceChunk(
                            doc_id=chunk.get("doc_id", ""),
                            file_name=chunk.get("file_name", ""),
                            page=chunk.get("page_number", chunk.get("page", 1)),
                            chunk_id=chunk.get("chunk_id", ""),
                            char_start=chunk.get("char_start", 0),
                            char_end=chunk.get("char_end", 0),
                            text=chunk.get("text", "")[:200]
                        ))
                
                q_type = data.get("question_type", "short")
                if q_type not in [qt.value for qt in QuestionType]:
                    q_type = question_types[0].value if question_types else "short"
                
                return GeneratedQuestion(
                    question_id=data.get("question_id", str(uuid.uuid4())),
                    question_text=data.get("question_text", ""),
                    question_type=QuestionType(q_type),
                    options=data.get("options"),
                    correct_answer=str(data.get("correct_answer", "")),
                    solution_steps=data.get("solution_steps", ""),
                    source_chunks=source_chunks
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse DeepSeek response: {e}")
        
        return self._generate_fallback_question(chunks, question_types, difficulty)
    
    def _generate_fallback_question(
        self,
        chunks: List[Dict],
        question_types: List[QuestionType],
        difficulty: Difficulty
    ) -> GeneratedQuestion:
        q_type = question_types[0] if question_types else QuestionType.SHORT
        
        if chunks:
            chunk = chunks[0]
            text_snippet = chunk.get("text", "")[:100]
            source_chunks = [SourceChunk(
                doc_id=chunk.get("doc_id", ""),
                file_name=chunk.get("file_name", "sample.txt"),
                page=chunk.get("page_number", 1),
                chunk_id=chunk.get("chunk_id", str(uuid.uuid4())),
                char_start=chunk.get("char_start", 0),
                char_end=chunk.get("char_end", 100),
                text=text_snippet
            )]
        else:
            text_snippet = "study material"
            source_chunks = []
        
        if q_type == QuestionType.MCQ:
            return GeneratedQuestion(
                question_text=f"Based on the study material, which concept is most important?",
                question_type=q_type,
                options=["A. The first principle", "B. The second principle", "C. The third principle", "D. All of the above"],
                correct_answer="D",
                solution_steps="The correct answer is D because all principles are equally important.",
                source_chunks=source_chunks
            )
        elif q_type == QuestionType.CALC:
            return GeneratedQuestion(
                question_text="Calculate: What is 15 * 4 + 20?",
                question_type=q_type,
                options=None,
                correct_answer="80",
                solution_steps="Step 1: 15 * 4 = 60\nStep 2: 60 + 20 = 80",
                source_chunks=source_chunks
            )
        else:
            return GeneratedQuestion(
                question_text=f"Briefly explain the main concept from this material: '{text_snippet}...'",
                question_type=q_type,
                options=None,
                correct_answer="The main concept involves understanding the fundamental principles presented in the text.",
                solution_steps="Review the text and identify the key principles mentioned.",
                source_chunks=source_chunks
            )
    
    async def verify_answer(
        self,
        chunks: List[Dict],
        correct_answer: str,
        solution: str,
        student_answer: str,
        question_type: QuestionType
    ) -> VerificationResult:
        if question_type == QuestionType.MCQ:
            student_clean = student_answer.strip().upper()
            correct_clean = correct_answer.strip().upper()
            
            if len(student_clean) > 0:
                student_clean = student_clean[0]
            if len(correct_clean) > 0:
                correct_clean = correct_clean[0]
            
            is_correct = student_clean == correct_clean
            
            citations = []
            if chunks:
                chunk = chunks[0]
                citations.append(SourceChunk(
                    doc_id=chunk.get("doc_id", ""),
                    file_name=chunk.get("file_name", ""),
                    page=chunk.get("page_number", chunk.get("page", 1)),
                    chunk_id=chunk.get("chunk_id", ""),
                    char_start=chunk.get("char_start", 0),
                    char_end=chunk.get("char_end", 0)
                ))
            
            return VerificationResult(
                correct=is_correct,
                confidence=1.0,
                explanation=f"Your answer '{student_answer}' is {'correct' if is_correct else f'incorrect. The correct answer is {correct_answer}'}.",
                citation=citations
            )
        
        context = self._format_context(chunks) if chunks else "No context available"
        
        prompt = VERIFY_ANSWER_PROMPT.format(
            context=context,
            solution=solution,
            correct_answer=correct_answer,
            student_answer=student_answer
        )
        
        response = await self._call_deepseek(prompt)
        
        if response:
            try:
                data = json.loads(response)
                
                citations = []
                for c in data.get("citation", []):
                    citations.append(SourceChunk(
                        doc_id=c.get("doc_id", ""),
                        file_name=c.get("file_name", ""),
                        page=c.get("page", 1),
                        chunk_id=c.get("chunk_id", ""),
                        char_start=0,
                        char_end=0
                    ))
                
                return VerificationResult(
                    correct=data.get("correct", False),
                    confidence=float(data.get("confidence", 0.5)),
                    explanation=data.get("explanation", ""),
                    citation=citations
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse verification response: {e}")
        
        student_lower = student_answer.lower().strip()
        correct_lower = correct_answer.lower().strip()
        
        is_correct = student_lower == correct_lower or correct_lower in student_lower
        
        return VerificationResult(
            correct=is_correct,
            confidence=0.7 if is_correct else 0.5,
            explanation=f"Answer comparison: {'Match found' if is_correct else 'No match'}. Expected: {correct_answer}",
            citation=[]
        )
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


generator = DeepSeekGenerator()
