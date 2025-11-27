from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid


class QuestionType(str, Enum):
    MCQ = "mcq"
    SHORT = "short"
    CALC = "calc"
    CODE = "code"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SourceChunk(BaseModel):
    doc_id: str
    file_name: str
    page: int
    chunk_id: str
    char_start: int
    char_end: int
    text: Optional[str] = None


class ChunkMetadata(BaseModel):
    doc_id: str
    file_name: str
    page_number: int
    chunk_id: str
    char_start: int
    char_end: int


class UploadResponse(BaseModel):
    course_id: str
    files: List[str]
    chunks_indexed: int


class CreateMatchRequest(BaseModel):
    course_id: str
    player_name: str
    time_limit_seconds: int = 30
    question_types: List[QuestionType] = [QuestionType.SHORT, QuestionType.CALC]
    difficulty: Difficulty = Difficulty.MEDIUM


class CreateMatchResponse(BaseModel):
    match_id: str
    websocket_url: str
    waiting_for_opponent: bool


class JoinMatchRequest(BaseModel):
    match_id: str
    player_name: str


class JoinMatchResponse(BaseModel):
    success: bool
    message: str
    match_id: str


class AnswerRequest(BaseModel):
    match_id: str
    question_id: str
    player_name: str
    answer_payload: str


class AnswerResponse(BaseModel):
    correct: bool
    damage_dealt: int
    your_hp: int
    opponent_hp: int
    explanation: str
    citation: Optional[List[SourceChunk]] = None


class GeneratedQuestion(BaseModel):
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_text: str
    question_type: QuestionType
    options: Optional[List[str]] = None
    correct_answer: str
    solution_steps: str
    source_chunks: List[SourceChunk]
    time_limit: int = 30


class VerificationResult(BaseModel):
    correct: bool
    confidence: float
    explanation: str
    citation: List[SourceChunk]


class Player(BaseModel):
    name: str
    hp: int = 100
    last_submission_time: Optional[float] = None
    cooldown_until: Optional[float] = None
    submitted_this_round: bool = False


class CurrentRound(BaseModel):
    question_id: str
    question: GeneratedQuestion
    start_time: float
    time_limit: int
    answers_received: Dict[str, Any] = {}


class Match(BaseModel):
    match_id: str
    course_id: str
    players: Dict[str, Player] = {}
    current_round: Optional[CurrentRound] = None
    rounds_history: List[Dict[str, Any]] = []
    time_limit_seconds: int = 30
    question_types: List[QuestionType] = [QuestionType.SHORT]
    difficulty: Difficulty = Difficulty.MEDIUM
    status: str = "waiting"
    winner: Optional[str] = None


class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any] = {}


class CourseInfo(BaseModel):
    course_id: str
    files: List[str]
    total_chunks: int
    created_at: float
