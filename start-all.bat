@echo off
echo Starting AI Surveillance System...

echo Starting AI Service (Python/FastAPI) on Port 8000...
start cmd /k "cd ai-service && title AI-Service && ..\.venv311\Scripts\uvicorn.exe app:app --host 0.0.0.0 --port 8000"

echo Starting Backend Service (Node.js) on Port 5000...
start cmd /k "cd backend && title Backend && node server.js"


echo Starting Frontend Service (React/Vite) on Port 5173...
start cmd /k "cd frontend && title Frontend && npm run dev"

echo All services are starting up! 
echo Once they load, you can access the frontend at http://localhost:5173
pause
