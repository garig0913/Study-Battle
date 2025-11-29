import os
import json
import uuid
import aiohttp
import logging
import random
from typing import List, Dict, Optional
from models import GeneratedQuestion, VerificationResult, SourceChunk, QuestionType, Difficulty

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

GENERATE_PROBLEM_PROMPT = """You are a math/CS exam writer. ONLY use the provided context. Create ONE concise, student-friendly problem solvable with the context.

Output JSON ONLY with these keys:
{{
  "question_id": "<uuid>",
  "question_text": "...",
  "question_type": "mcq|short|calc|code",
  "options": ["A ...", "B ...", "C ...", "D ..."] OR null,
  "correct_answer": "...",
  "solution_steps": "...",
  "source_chunks": [{{"file_name":"", "page":1, "chunk_id": "..."}}]
}}

Requirements:
- question_type must be one of: {question_types}
- difficulty level: {difficulty}
- For MCQ: exactly 4 options (A–D)
- For short/calc/code: options must be null
- question_text ≤ 200 characters; do not paste long context quotes
- solution_steps must be clear and step-by-step
- source_chunks must reference real chunks from Context

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

ANSWER_QA_PROMPT = """You are a helpful tutor. Use ONLY the provided context chunks to answer the user's question concisely.

Return JSON ONLY:
{{
  "answer": "...",
  "citation": [{{"file_name":"", "page":1, "chunk_id":"..."}}]
}}

Context:
{context}

User Question: {question}
"""

EXTRACT_CONCEPTS_PROMPT = """You are a course curator. Read the full context and extract the MAIN CONCEPTS.

Return JSON ONLY:
{{
  "concepts": [
    {{ "name": "...", "summary": "..." }},
    ...
  ]
}}

Rules:
- 5–10 concise concepts
- Names should be human-readable titles (no formulas or raw statements)
- Summaries ≤ 40 words, clear and student-friendly
- Use ONLY what appears in the context

Context:
{context}
"""

def _extract_concept_name(text: str) -> str:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    import re
    def clean_candidate(s: str) -> str:
        s = s.strip()
        if ":" in s:
            s = s.split(":", 1)[0].strip()
        s = re.sub(r"[^A-Za-z0-9\s\-]", "", s)
        s = re.sub(r"\s+", " ", s)
        return s[:80]
    keywords = ["Definition", "Rule", "Theorem", "Axiom", "Example", "Property", "Concept"]
    for l in lines[:8]:
        for k in keywords:
            if k.lower() in l.lower():
                c = clean_candidate(l)
                if len(c.split()) >= 2:
                    return c
        if sum(1 for w in l.split() if w[:1].isupper()) >= 2 and len(l.split()) <= 12:
            c = clean_candidate(l)
            if len(c.split()) >= 2:
                return c
    m = re.search(r"([A-Z][A-Za-z]+(\s+[A-Z][A-Za-z]+)+)", text or "")
    if m:
        return clean_candidate(m.group(1))
    words = (text or "").split()
    fallback = " ".join(words[:6]) if words else "main concept"
    return clean_candidate(fallback) or "main concept"

def _curated_concept(text: str) -> Optional[str]:
    t = (text or "").lower()
    if "∃" in text or "exists" in t or "existential" in t:
        return "Existential quantifier (∃)"
    if "∀" in text or "for all" in t or "universal" in t:
        return "Universal quantifier (∀)"
    if "predicate" in t and ("calculus" in t or "first" in t or "order" in t):
        return "First-order predicate calculus (FOPC)"
    if "model" in t and "fopc" in t:
        return "Models in FOPC"
    if "domain of discourse" in t or "domain" in t:
        return "Domain of discourse"
    if "resolution" in t:
        return "Resolution"
    if "unification" in t:
        return "Unification"
    if "skolem" in t:
        return "Skolemization"
    if "knowledge representation" in t or "kr" in t:
        return "Knowledge representation"
    if "semantics" in t:
        return "Semantics"
    if "syntax" in t:
        return "Syntax"
    return None


class DeepSeekGenerator:
    
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.model = "deepseek-chat"
        self._session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _call_deepseek(self, prompt: str, max_retries: int = 1) -> Optional[str]:
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
                    timeout=aiohttp.ClientTimeout(total=12)
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
            chunk_info += f"Content: {chunk.get('text', '')[:800]}\n"
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
        
        concepts = await self.extract_concepts(chunks)
        if concepts:
            concept = random.choice(concepts)
            if question_types and QuestionType.SHORT in question_types:
                q_type = QuestionType.SHORT
            elif question_types and QuestionType.MCQ in question_types:
                q_type = QuestionType.MCQ
            else:
                q_type = QuestionType.SHORT
            base_chunk = chunks[0]
            source_chunks = [SourceChunk(
                doc_id=base_chunk.get("doc_id", ""),
                file_name=base_chunk.get("file_name", ""),
                page=base_chunk.get("page_number", base_chunk.get("page", 1)),
                chunk_id=base_chunk.get("chunk_id", ""),
                char_start=base_chunk.get("char_start", 0),
                char_end=base_chunk.get("char_end", 0),
                text=base_chunk.get("text", "")[:200]
            )]
            if q_type == QuestionType.MCQ:
                opts = [
                    f"A. {concept['summary']}",
                    "B. A tangential topic",
                    "C. An unrelated definition",
                    "D. None of the above"
                ]
                return GeneratedQuestion(
                    question_id=str(uuid.uuid4()),
                    question_text=f"Which option best defines the concept '{concept['name']}'?",
                    question_type=q_type,
                    options=opts,
                    correct_answer="A",
                    solution_steps="Choose the option that matches the concept definition.",
                    source_chunks=source_chunks
                )
            return GeneratedQuestion(
                question_id=str(uuid.uuid4()),
                question_text=f"Explain the concept: '{concept['name']}'.",
                question_type=q_type,
                options=None,
                correct_answer=concept['summary'],
                solution_steps="Name the concept and give its concise definition and role.",
                source_chunks=source_chunks
            )
        context = self._format_context(chunks)
        types_str = ", ".join([qt.value for qt in question_types])
        prompt = GENERATE_PROBLEM_PROMPT.format(
            question_types=types_str,
            difficulty=difficulty.value,
            context=context
        )
        response = await self._call_deepseek(prompt, max_retries=1)
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
        preferred = [t for t in (question_types or []) if t != QuestionType.CALC]
        if preferred:
            q_type = preferred[0]
        elif question_types:
            q_type = question_types[0]
        else:
            q_type = QuestionType.SHORT
        
        if chunks:
            chunk = random.choice(chunks)
            text_snippet = chunk.get("text", "")[:280]
            source_chunks = [SourceChunk(
                doc_id=chunk.get("doc_id", ""),
                file_name=chunk.get("file_name", "sample.txt"),
                page=chunk.get("page_number", 1),
                chunk_id=chunk.get("chunk_id", str(uuid.uuid4())),
                char_start=chunk.get("char_start", 0),
                char_end=chunk.get("char_end", 280),
                text=text_snippet
            )]
        else:
            text_snippet = "study material"
            source_chunks = []
        
        if q_type == QuestionType.MCQ:
            return GeneratedQuestion(
                question_text=f"Based on the material, which concept is most emphasized?",
                question_type=q_type,
                options=["A. The first principle", "B. The second principle", "C. The third principle", "D. All of the above"],
                correct_answer="D",
                solution_steps="The correct answer is D because all principles are equally important.",
                source_chunks=source_chunks
            )
        elif q_type == QuestionType.CALC:
            # Only used when CALC is the only requested type
            a = random.randint(10, 30)
            b = random.randint(2, 9)
            c = random.randint(10, 40)
            calc_answer = str(a * b + c)
            return GeneratedQuestion(
                question_text=f"Calculate: What is {a} * {b} + {c}?",
                question_type=q_type,
                options=None,
                correct_answer=calc_answer,
                solution_steps=f"Step 1: {a} * {b} = {a * b}\nStep 2: {a * b} + {c} = {a * b + c}",
                source_chunks=source_chunks
            )
        else:
            concept = _curated_concept(text_snippet) or _extract_concept_name(text_snippet)
            definitions = {
                "Existential quantifier (∃)": "∃x P means there exists at least one object x such that P holds.",
                "Universal quantifier (∀)": "∀x P means for all objects x in the domain, P holds.",
                "First-order predicate calculus (FOPC)": "A logical system with quantifiers over objects, predicates, and variables for expressing statements about a domain.",
                "Models in FOPC": "An interpretation assigning a domain and meanings to predicates/functions so formulas have truth values.",
                "Domain of discourse": "The set of objects that variables range over in a logical interpretation.",
                "Resolution": "A rule of inference used for automated reasoning by deriving contradictions to prove statements.",
                "Unification": "The process of making two expressions identical by finding substitutions for variables.",
                "Skolemization": "Eliminating existential quantifiers by introducing Skolem functions or constants.",
                "Knowledge representation": "Techniques to encode information about the world in a form that a computer can utilize to solve complex tasks.",
                "Semantics": "The meaning of symbols and formulas; how interpretations assign truth values.",
                "Syntax": "The formal structure and rules for forming well-constructed expressions and formulas."
            }
            answer_text = definitions.get(concept, "Provide a concise definition and role of the concept.")
            steps = (
                f"1) Name the concept: {concept}\n"
                f"2) Define it precisely\n"
                f"3) Explain its role in the material"
            )
            return GeneratedQuestion(
                question_text=f"Explain the concept: '{concept}'.",
                question_type=q_type,
                options=None,
                correct_answer=answer_text,
                solution_steps=steps,
                source_chunks=source_chunks
            )
    
    async def extract_concepts(self, chunks: List[Dict]) -> List[Dict]:
        context = self._format_context(chunks) if chunks else ""
        if not context:
            return []
        prompt = EXTRACT_CONCEPTS_PROMPT.format(context=context)
        response = await self._call_deepseek(prompt, max_retries=1)
        if not response:
            return []
        try:
            data = json.loads(response)
            concepts = data.get("concepts") or []
            results = []
            import re
            def clean_name(name: str) -> str:
                # Remove page markers, excessive digits, and repeated tokens
                n = name.strip()
                n = re.sub(r"\bP\d+\b", "", n)  # remove tokens like P317
                n = re.sub(r"[^A-Za-z0-9\s\-]", "", n)
                n = re.sub(r"\s+", " ", n)
                tokens = n.split()
                # drop single-letter or pure-digit tokens
                tokens = [t for t in tokens if (len(t) > 1 and not t.isdigit())]
                # dedupe consecutive tokens
                dedup = []
                for t in tokens:
                    if not dedup or dedup[-1].lower() != t.lower():
                        dedup.append(t)
                n = " ".join(dedup)
                return n.strip()[:80]
            for c in concepts:
                raw_name = (c.get("name") or "").strip()
                summary = (c.get("summary") or "").strip()
                name = clean_name(raw_name)
                # basic validity checks
                if not name or len(name.split()) < 2:
                    continue
                if summary and len(summary) > 0:
                    results.append({"name": name, "summary": summary})
            # dedupe by name
            seen = set()
            deduped = []
            for item in results:
                key = item["name"].lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
            return deduped
        except json.JSONDecodeError:
            return []

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
                explanation="Correct." if is_correct else "Incorrect.",
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
                
                is_correct = bool(data.get("correct", False))
                return VerificationResult(
                    correct=is_correct,
                    confidence=float(data.get("confidence", 0.5)),
                    explanation="Correct." if is_correct else "Incorrect.",
                    citation=citations if is_correct else []
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse verification response: {e}")
        
        student_lower = student_answer.lower().strip()
        correct_lower = correct_answer.lower().strip()
        
        is_correct = student_lower == correct_lower or correct_lower in student_lower
        
        return VerificationResult(
            correct=is_correct,
            confidence=0.7 if is_correct else 0.5,
            explanation="Correct." if is_correct else "Incorrect.",
            citation=[]
        )

    async def answer_question(
        self,
        chunks: List[Dict],
        question: str
    ) -> Dict:
        context = self._format_context(chunks) if chunks else "No context available"
        prompt = ANSWER_QA_PROMPT.format(context=context, question=question)
        response = await self._call_deepseek(prompt, max_retries=1)
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
                ans = (data.get("answer", "") or "").strip()
                if not ans:
                    # provide concise fallback from top chunk
                    if chunks:
                        snippet = chunks[0].get("text", "").strip()[:300]
                        ans = snippet or "No context available"
                        citations = [SourceChunk(
                            doc_id=chunks[0].get("doc_id", ""),
                            file_name=chunks[0].get("file_name", ""),
                            page=chunks[0].get("page_number", chunks[0].get("page", 1)),
                            chunk_id=chunks[0].get("chunk_id", ""),
                            char_start=chunks[0].get("char_start", 0),
                            char_end=chunks[0].get("char_end", 0)
                        )]
                    else:
                        ans = "No context available"
                return {
                    "answer": ans,
                    "citation": citations
                }
            except json.JSONDecodeError:
                pass
        if chunks:
            snippet = chunks[0].get("text", "")[:300]
            return {
                "answer": snippet,
                "citation": [SourceChunk(
                    doc_id=chunks[0].get("doc_id", ""),
                    file_name=chunks[0].get("file_name", ""),
                    page=chunks[0].get("page_number", chunks[0].get("page", 1)),
                    chunk_id=chunks[0].get("chunk_id", ""),
                    char_start=chunks[0].get("char_start", 0),
                    char_end=chunks[0].get("char_end", 0)
                )]
            }
        return {"answer": "No context available", "citation": []}
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


generator = DeepSeekGenerator()
