import os
import sys
import time
import uuid
import json
import asyncio
import logging
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from models import (
    Match, Player, CurrentRound, GeneratedQuestion,
    CreateMatchRequest, CreateMatchResponse,
    JoinMatchRequest, JoinMatchResponse,
    AnswerRequest, AnswerResponse,
    UploadResponse, QuestionType, Difficulty, SourceChunk
)
from storage import file_storage
from rag import rag_pipeline
from generator import generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HP_MAX = 100
BASE_DAMAGE = 20
MAX_BONUS = 30
TIMEOUT_PENALTY = 8
COOLDOWN_SECONDS = 2

matches: Dict[str, Match] = {}
websocket_connections: Dict[str, Dict[str, WebSocket]] = {}
round_timers: Dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Study-Battle server starting...")
    yield
    await generator.close()
    logger.info("Study-Battle server shutdown")


app = FastAPI(
    title="Study-Battle API",
    description="Real-time competitive learning platform with RAG",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def calculate_damage(time_limit: int, seconds_taken: float) -> int:
    speed_ratio = max(0, (time_limit - seconds_taken) / time_limit)
    bonus = round(MAX_BONUS * speed_ratio)
    damage = BASE_DAMAGE + bonus
    return damage


async def broadcast_to_match(match_id: str, message: dict, exclude_player: str = None):
    if match_id not in websocket_connections:
        return
    
    message_json = json.dumps(message)
    for player_name, ws in websocket_connections[match_id].items():
        if exclude_player and player_name == exclude_player:
            continue
        try:
            await ws.send_text(message_json)
        except Exception as e:
            logger.error(f"Failed to send to {player_name}: {e}")


async def send_to_player(match_id: str, player_name: str, message: dict):
    if match_id in websocket_connections:
        if player_name in websocket_connections[match_id]:
            try:
                await websocket_connections[match_id][player_name].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send to {player_name}: {e}")


async def run_round_timer(match_id: str):
    if match_id not in matches:
        return
    
    match = matches[match_id]
    if not match.current_round:
        return
    
    time_limit = match.current_round.time_limit
    start_time = match.current_round.start_time
    
    while True:
        await asyncio.sleep(1)
        
        if match_id not in matches:
            break
        
        match = matches[match_id]
        if not match.current_round or match.current_round.question_id != matches[match_id].current_round.question_id:
            break
        
        elapsed = time.time() - start_time
        seconds_left = max(0, int(time_limit - elapsed))
        
        await broadcast_to_match(match_id, {
            "type": "round_update",
            "data": {"seconds_left": seconds_left}
        })
        
        if seconds_left <= 0:
            await handle_round_timeout(match_id)
            break


async def handle_round_timeout(match_id: str):
    if match_id not in matches:
        return
    
    match = matches[match_id]
    if not match.current_round:
        return
    
    for player_name in match.players:
        if not match.players[player_name].submitted_this_round:
            match.players[player_name].hp = max(0, match.players[player_name].hp - TIMEOUT_PENALTY)
    
    question = match.current_round.question
    
    await broadcast_to_match(match_id, {
        "type": "round_result",
        "data": {
            "timeout": True,
            "winner_player": None,
            "damage": TIMEOUT_PENALTY,
            "solution": question.solution_steps,
            "correct_answer": question.correct_answer,
            "citation": [sc.model_dump() for sc in question.source_chunks],
            "players": {name: {"hp": p.hp} for name, p in match.players.items()}
        }
    })
    
    match.current_round = None
    
    for player in match.players.values():
        player.submitted_this_round = False
    
    game_over = any(p.hp <= 0 for p in match.players.values())
    
    if game_over:
        await end_match(match_id)
    else:
        await asyncio.sleep(3)
        await start_new_round(match_id)


async def start_new_round(match_id: str):
    if match_id not in matches:
        return
    
    match = matches[match_id]
    
    if match.status != "active":
        return
    
    chunks = rag_pipeline.get_all_chunks(match.course_id)
    
    question = await generator.generate_question(
        chunks=chunks[:10],
        question_types=match.question_types,
        difficulty=match.difficulty
    )
    
    if not question:
        await broadcast_to_match(match_id, {
            "type": "error",
            "data": {"message": "Failed to generate question"}
        })
        return
    
    question.time_limit = match.time_limit_seconds
    
    match.current_round = CurrentRound(
        question_id=question.question_id,
        question=question,
        start_time=time.time(),
        time_limit=match.time_limit_seconds
    )
    
    for player in match.players.values():
        player.submitted_this_round = False
    
    question_data = {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "question_type": question.question_type.value,
        "options": question.options,
        "time_limit": question.time_limit
    }
    
    await broadcast_to_match(match_id, {
        "type": "round_start",
        "data": question_data
    })
    
    if match_id in round_timers:
        round_timers[match_id].cancel()
    
    round_timers[match_id] = asyncio.create_task(run_round_timer(match_id))


async def end_match(match_id: str):
    if match_id not in matches:
        return
    
    match = matches[match_id]
    match.status = "finished"
    
    winner = None
    for name, player in match.players.items():
        if player.hp > 0:
            winner = name
            break
    
    if not winner:
        max_hp = max(p.hp for p in match.players.values())
        for name, player in match.players.items():
            if player.hp == max_hp:
                winner = name
                break
    
    match.winner = winner
    
    await broadcast_to_match(match_id, {
        "type": "match_end",
        "data": {
            "winner": winner,
            "final_hp": {name: p.hp for name, p in match.players.items()}
        }
    })
    
    if match_id in round_timers:
        round_timers[match_id].cancel()


@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    file_data = []
    for file in files:
        content = await file.read()
        file_data.append((file.filename, content, file.content_type))
    
    course_id, processed_files, chunks = await file_storage.save_and_process_files(file_data)
    
    if chunks:
        indexed_count = await rag_pipeline.index_chunks(course_id, chunks)
    else:
        indexed_count = 0
    
    return UploadResponse(
        course_id=course_id,
        files=processed_files,
        chunks_indexed=indexed_count
    )


@app.post("/api/create-match", response_model=CreateMatchResponse)
async def create_match(request: CreateMatchRequest):
    match_id = str(uuid.uuid4())[:8]
    
    course_info = file_storage.get_course_info(request.course_id)
    if not course_info:
        raise HTTPException(status_code=404, detail="Course not found")
    
    match = Match(
        match_id=match_id,
        course_id=request.course_id,
        time_limit_seconds=request.time_limit_seconds,
        question_types=request.question_types,
        difficulty=request.difficulty,
        status="waiting"
    )
    
    match.players[request.player_name] = Player(name=request.player_name)
    
    matches[match_id] = match
    websocket_connections[match_id] = {}
    
    return CreateMatchResponse(
        match_id=match_id,
        websocket_url=f"/ws/{match_id}",
        waiting_for_opponent=True
    )


@app.post("/api/join-match", response_model=JoinMatchResponse)
async def join_match(request: JoinMatchRequest):
    if request.match_id not in matches:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match = matches[request.match_id]
    
    if len(match.players) >= 2:
        raise HTTPException(status_code=400, detail="Match is full")
    
    if request.player_name in match.players:
        raise HTTPException(status_code=400, detail="Player name already taken")
    
    match.players[request.player_name] = Player(name=request.player_name)
    
    return JoinMatchResponse(
        success=True,
        message="Joined match successfully",
        match_id=request.match_id
    )


@app.post("/api/answer", response_model=AnswerResponse)
async def submit_answer(request: AnswerRequest):
    if request.match_id not in matches:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match = matches[request.match_id]
    
    if request.player_name not in match.players:
        raise HTTPException(status_code=400, detail="Player not in match")
    
    if not match.current_round:
        raise HTTPException(status_code=400, detail="No active round")
    
    if match.current_round.question_id != request.question_id:
        raise HTTPException(status_code=400, detail="Invalid question ID")
    
    player = match.players[request.player_name]
    
    if player.submitted_this_round:
        raise HTTPException(status_code=400, detail="Already submitted this round")
    
    if player.cooldown_until and time.time() < player.cooldown_until:
        raise HTTPException(status_code=400, detail="In cooldown")
    
    question = match.current_round.question
    time_taken = time.time() - match.current_round.start_time
    
    chunks = rag_pipeline.get_all_chunks(match.course_id)[:5]
    
    verification = await generator.verify_answer(
        chunks=chunks,
        correct_answer=question.correct_answer,
        solution=question.solution_steps,
        student_answer=request.answer_payload,
        question_type=question.question_type
    )
    
    opponent_name = [n for n in match.players.keys() if n != request.player_name][0]
    
    if verification.correct:
        player.submitted_this_round = True
        damage = calculate_damage(match.current_round.time_limit, time_taken)
        
        match.players[opponent_name].hp = max(0, match.players[opponent_name].hp - damage)
        
        match.current_round.answers_received[request.player_name] = {
            "correct": True,
            "time_taken": time_taken,
            "damage": damage
        }
        
        if request.match_id in round_timers:
            round_timers[request.match_id].cancel()
        
        await broadcast_to_match(request.match_id, {
            "type": "round_result",
            "data": {
                "winner_player": request.player_name,
                "loser_player": opponent_name,
                "damage": damage,
                "time_taken": round(time_taken, 2),
                "solution": question.solution_steps,
                "correct_answer": question.correct_answer,
                "citation": [sc.model_dump() for sc in question.source_chunks],
                "players": {name: {"hp": p.hp} for name, p in match.players.items()}
            }
        })
        
        match.current_round = None
        
        game_over = any(p.hp <= 0 for p in match.players.values())
        
        if game_over:
            await end_match(request.match_id)
        else:
            await asyncio.sleep(3)
            await start_new_round(request.match_id)
        
        return AnswerResponse(
            correct=True,
            damage_dealt=damage,
            your_hp=player.hp,
            opponent_hp=match.players[opponent_name].hp,
            explanation=verification.explanation,
            citation=verification.citation
        )
    else:
        player.cooldown_until = time.time() + COOLDOWN_SECONDS
        
        await send_to_player(request.match_id, request.player_name, {
            "type": "answer_feedback",
            "data": {
                "correct": False,
                "explanation": verification.explanation,
                "cooldown_seconds": COOLDOWN_SECONDS
            }
        })
        
        return AnswerResponse(
            correct=False,
            damage_dealt=0,
            your_hp=player.hp,
            opponent_hp=match.players[opponent_name].hp,
            explanation=verification.explanation,
            citation=verification.citation
        )


@app.get("/api/match/{match_id}")
async def get_match_info(match_id: str):
    if match_id not in matches:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match = matches[match_id]
    return {
        "match_id": match.match_id,
        "status": match.status,
        "players": {name: {"hp": p.hp} for name, p in match.players.items()},
        "time_limit": match.time_limit_seconds,
        "winner": match.winner
    }


@app.get("/api/courses")
async def list_courses():
    courses = []
    for course_id, info in file_storage.courses.items():
        courses.append({
            "course_id": course_id,
            "files": info.get("files", []),
            "chunk_count": len(info.get("chunks", []))
        })
    return {"courses": courses}


@app.websocket("/ws/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str):
    await websocket.accept()
    
    player_name = websocket.query_params.get("player")
    
    if not player_name:
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": "Player name required"}
        }))
        await websocket.close()
        return
    
    if match_id not in matches:
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": "Match not found"}
        }))
        await websocket.close()
        return
    
    match = matches[match_id]
    
    if player_name not in match.players:
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": "Player not in match"}
        }))
        await websocket.close()
        return
    
    if match_id not in websocket_connections:
        websocket_connections[match_id] = {}
    
    websocket_connections[match_id][player_name] = websocket
    
    await websocket.send_text(json.dumps({
        "type": "connected",
        "data": {
            "player": player_name,
            "match_id": match_id,
            "players": list(match.players.keys())
        }
    }))
    
    # If match is already active, send ready state immediately
    if match.status == "active":
        await websocket.send_text(json.dumps({
            "type": "match_ready",
            "data": {
                "players": {name: {"hp": p.hp} for name, p in match.players.items()}
            }
        }))
        # If there's a current question, send it to the reconnected player
        if match.current_question:
            await websocket.send_text(json.dumps({
                "type": "round_start",
                "data": match.current_question.model_dump()
            }))
    # Otherwise check if we now have 2 players to start the match
    elif len(websocket_connections[match_id]) == 2 and match.status == "waiting":
        match.status = "active"
        
        await broadcast_to_match(match_id, {
            "type": "match_ready",
            "data": {
                "players": {name: {"hp": p.hp} for name, p in match.players.items()}
            }
        })
        
        await asyncio.sleep(2)
        await start_new_round(match_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "submit_answer":
                answer_data = message.get("data", {})
                try:
                    await submit_answer(AnswerRequest(
                        match_id=match_id,
                        question_id=answer_data.get("question_id", ""),
                        player_name=player_name,
                        answer_payload=answer_data.get("answer", "")
                    ))
                except HTTPException as e:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "data": {"message": e.detail}
                    }))
            
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    
    except WebSocketDisconnect:
        logger.info(f"Player {player_name} disconnected from match {match_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if match_id in websocket_connections:
            websocket_connections[match_id].pop(player_name, None)


if os.path.exists("frontend/dist"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)
        return FileResponse("frontend/dist/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
