# Study Battle - Project Documentation

## Overview
Study Battle is a real-time competitive learning platform where two players compete by solving AI-generated problems from uploaded study materials. The app uses RAG (Retrieval-Augmented Generation) with Zilliz Cloud/Milvus for vector storage, DeepSeek for question generation and verification, and LlamaIndex for the RAG pipeline.

## Current State
- **Status**: MVP Complete
- **Last Updated**: November 2024

## Architecture

### Backend (Python FastAPI)
- **Port**: 8000
- **Location**: `/backend/`
- **Key Files**:
  - `main.py` - FastAPI server with WebSocket support for real-time battles
  - `rag.py` - LlamaIndex RAG pipeline with Milvus/Zilliz integration
  - `generator.py` - DeepSeek integration for question generation and answer verification
  - `models.py` - Pydantic data models
  - `storage.py` - File upload and text extraction utilities

### Frontend (React + Vite)
- **Port**: 5000
- **Location**: `/frontend/`
- **Pages**:
  - Upload - File upload for study materials
  - Lobby - Match creation and joining
  - Arena - Real-time battle interface

## Key Features
1. Document upload (PDF, DOCX, PPTX, TXT, images)
2. RAG-based question generation from study materials
3. Real-time WebSocket battles with health bars
4. Speed-based damage calculation
5. Source citation for every question

## Environment Variables Required
- `DEEPSEEK_API_KEY` - Required for question generation
- `OPENAI_API_KEY` - Optional for embeddings (recommended)
- `ZILLIZ_URI` - Optional for cloud vector storage
- `ZILLIZ_TOKEN` - Optional for cloud vector storage

## Running the App
The app runs automatically with two workflows:
1. Backend Server (port 8000)
2. Frontend Dev Server (port 5000 - user-facing)

## Game Mechanics
- **HP**: Each player starts with 100 HP
- **Damage**: Base 20 + speed bonus (up to 30)
- **Formula**: `damage = 20 + round(30 * (time_limit - time_taken) / time_limit)`
- **Timeout**: 8 damage to both players if time expires

## API Endpoints
- `POST /api/upload` - Upload study materials
- `POST /api/create-match` - Create a new match
- `POST /api/join-match` - Join an existing match
- `POST /api/answer` - Submit an answer
- `GET /api/courses` - List available courses
- `GET /api/match/{match_id}` - Get match status
- `WS /ws/{match_id}?player=NAME` - WebSocket for real-time updates

## Sample Data
Located in `/sample_data/linear_algebra_basics.txt` for demo purposes.

## User Preferences
- No specific preferences recorded yet

## Recent Changes
- Initial MVP implementation
- Python FastAPI backend with WebSocket support
- React frontend with Upload, Lobby, and Arena pages
- LlamaIndex + Milvus RAG pipeline
- DeepSeek integration for question generation
