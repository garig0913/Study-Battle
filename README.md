# Study Battle

A real-time competitive learning platform powered by RAG (Retrieval-Augmented Generation). Two players compete by solving AI-generated problems from uploaded study materials.

## Features

- **Document Upload**: Support for PDF, DOCX, PPTX, TXT, and image files
- **RAG Pipeline**: LlamaIndex with Zilliz Cloud (Milvus) for intelligent chunking and retrieval
- **AI-Generated Questions**: DeepSeek generates new problems based on study materials
- **Real-time Battles**: WebSocket-powered competitive matches
- **Dynamic Damage System**: Speed-based damage calculation rewards quick answers
- **Source Citations**: Every question shows its source material for verification

## Tech Stack

- **Backend**: Python FastAPI + WebSocket
- **RAG**: LlamaIndex + Milvus/Zilliz Cloud
- **LLM**: DeepSeek for question generation and verification
- **Embeddings**: OpenAI text-embedding-3-small
- **Frontend**: React + Vite
- **Database**: In-memory (demo) or Zilliz Cloud (production)

## Environment Variables

Set these in your Replit Secrets:

| Variable | Required | Description |
|----------|----------|-------------|
| `ZILLIZ_URI` | Optional | Zilliz Cloud endpoint URL |
| `ZILLIZ_TOKEN` | Optional | Zilliz Cloud API token |
| `DEEPSEEK_API_KEY` | Required | DeepSeek API key for LLM |
| `OPENAI_API_KEY` | Optional | OpenAI key for embeddings |

### Getting API Keys

1. **DeepSeek API Key**: Sign up at [platform.deepseek.com](https://platform.deepseek.com)
2. **OpenAI API Key** (optional): Get from [platform.openai.com](https://platform.openai.com)
3. **Zilliz Cloud** (optional): Create free cluster at [cloud.zilliz.com](https://cloud.zilliz.com)

## Running the App

The app starts automatically in Replit. The frontend runs on port 5000 with a proxy to the backend on port 8000.

### API Endpoints

- `POST /api/upload` - Upload study materials
- `POST /api/create-match` - Create a new match
- `POST /api/join-match` - Join an existing match
- `POST /api/answer` - Submit an answer
- `GET /api/courses` - List available courses
- `GET /api/match/{match_id}` - Get match status
- `WS /ws/{match_id}?player=NAME` - WebSocket connection

## Demo Script (On-Stage)

### Setup (30 seconds)
1. Open the app in two browser windows/devices
2. Have sample_data/linear_algebra_basics.txt ready

### Demo Steps

1. **Upload** (Window A): 
   - Go to Upload page
   - Upload the sample linear algebra file
   - Note the course ID

2. **Create Match** (Window A):
   - Go to Lobby
   - Enter name "Player A"
   - Select the uploaded course
   - Set time limit to 30s
   - Click "Create Match"
   - Share match ID with Player B

3. **Join Match** (Window B):
   - Go to Lobby  
   - Enter name "Player B"
   - Enter the match ID
   - Click "Join Match"

4. **Battle!**
   - Both players see questions generated from the material
   - Race to answer correctly
   - Watch health bars decrease
   - First player to reduce opponent to 0 HP wins!

5. **K.O. Screen**
   - Show the winner
   - Discuss how RAG ensures accurate questions with citations

### What to Say

> "Study Battle uses RAG technology to generate fair, verifiable questions. Every problem comes directly from your study materials, with citations to the exact source. The AI creates new but similar problems - never verbatim copies - making it a true test of understanding."

## Damage Calculation

```
speed_ratio = max(0, (time_limit - seconds_taken) / time_limit)
bonus = round(30 * speed_ratio)
damage = 20 + bonus
```

Example: 30s time limit, answered in 6s
- speed_ratio = (30-6)/30 = 0.8
- bonus = round(30 * 0.8) = 24
- damage = 20 + 24 = 44 damage!

## Testing with cURL

```bash
# Upload a file
curl -X POST http://localhost:8000/api/upload \
  -F "files=@sample_data/linear_algebra_basics.txt"

# Create a match (use course_id from upload response)
curl -X POST http://localhost:8000/api/create-match \
  -H "Content-Type: application/json" \
  -d '{"course_id": "YOUR_COURSE_ID", "player_name": "TestPlayer", "time_limit_seconds": 30}'

# Join a match
curl -X POST http://localhost:8000/api/join-match \
  -H "Content-Type: application/json" \
  -d '{"match_id": "MATCH_ID", "player_name": "Player2"}'
```

## Project Structure

```
/backend
  main.py         # FastAPI server + WebSocket
  rag.py          # LlamaIndex RAG pipeline
  generator.py    # DeepSeek integration
  models.py       # Pydantic models
  storage.py      # File handling

/frontend
  src/
    pages/
      Upload.jsx  # File upload page
      Lobby.jsx   # Match creation/joining
      Arena.jsx   # Battle interface
    App.jsx       # Main app component

/sample_data
  linear_algebra_basics.txt  # Demo material
```

## License

MIT
