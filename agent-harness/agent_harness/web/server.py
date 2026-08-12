"""
FastAPI Web Server for Agent Harness.

Provides REST API and WebSocket for web frontend.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio
import json
import logging
import uvicorn

from agent_harness.core.harness import AgentHarness
from agent_harness.core.agent import BaseAgent, ActionResult

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")


# Global instances
harness: Optional[AgentHarness] = None
manager = ConnectionManager()


class WebAgent(BaseAgent):
    """Agent for web interface."""
    
    def __init__(self, **kwargs):
        super().__init__(name="web-agent", **kwargs)
        self.last_result = None
    
    async def think(self, observation):
        """Simple echo agent for demo."""
        task = observation.get("task", "")
        return {
            "action": "process",
            "input": task,
            "finish": True,
            "result": f"Processed: {task}",
        }
    
    async def act(self, thought):
        """Execute action."""
        result = thought.get("result", "")
        self.last_result = result
        return ActionResult(
            success=True,
            output=result,
            metadata={"task_complete": True},
        )


def create_app(agent_class=None, config: Dict[str, Any] = None) -> FastAPI:
    """Create FastAPI application."""
    global harness
    
    app = FastAPI(
        title="Agent Harness Web",
        description="Web interface for Agent Harness framework",
        version="1.0.0",
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Static files
    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    
    # Initialize harness on startup
    @app.on_event("startup")
    async def startup():
        global harness
        agent = agent_class() if agent_class else WebAgent()
        harness = AgentHarness(agent=agent, config=config or {
            "memory": {"enabled": True},
            "telemetry": {"enabled": True},
            "evolution": {"enabled": True},
        })
        await harness.initialize()
        logger.info("Agent Harness initialized for web")
    
    @app.on_event("shutdown")
    async def shutdown():
        global harness
        if harness:
            await harness.shutdown()
    
    # ===== Status API =====
    @app.get("/api/status")
    async def get_status():
        if harness:
            return harness.get_status()
        return {"initialized": False}
    
    # ===== Agent API =====
    @app.post("/api/agent/run")
    async def run_agent(data: dict):
        task = data.get("task", "")
        if not harness:
            return {"error": "Harness not initialized"}
        
        try:
            result = await harness.run(task)
            await manager.broadcast({
                "type": "task_complete",
                "task": task,
                "result": result,
            })
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @app.post("/api/agent/pause")
    async def pause_agent():
        if harness:
            await harness.pause()
            return {"success": True}
        return {"success": False, "error": "Not initialized"}
    
    @app.post("/api/agent/resume")
    async def resume_agent():
        if harness:
            await harness.resume()
            return {"success": True}
        return {"success": False, "error": "Not initialized"}
    
    @app.post("/api/agent/stop")
    async def stop_agent():
        if harness:
            await harness.stop()
            return {"success": True}
        return {"success": False, "error": "Not initialized"}
    
    # ===== Memory API =====
    @app.get("/api/memory/stats")
    async def get_memory_stats():
        if harness:
            return harness.get_memory_stats()
        return {}
    
    @app.get("/api/memory/search")
    async def search_memory(query: str, limit: int = 10):
        if harness and harness._memory:
            results = await harness._memory.retrieve(query, limit=limit)
            return {
                "results": [
                    {
                        "id": r.entry_id,
                        "content": r.content,
                        "importance": r.importance,
                        "tags": r.tags,
                    }
                    for r in results
                ]
            }
        return {"results": []}
    
    @app.post("/api/memory/consolidate")
    async def consolidate_memory():
        if harness and harness._memory:
            result = await harness._memory.consolidate()
            return result
        return {"error": "Memory not available"}
    
    # ===== Telemetry API =====
    @app.get("/api/telemetry/stats")
    async def get_telemetry_stats():
        if harness:
            return harness.get_telemetry_stats()
        return {}
    
    @app.get("/api/telemetry/sessions")
    async def get_sessions(limit: int = 50):
        if harness and harness._telemetry:
            sessions = await harness._telemetry.get_session_history(limit=limit)
            return {"sessions": sessions}
        return {"sessions": []}
    
    # ===== Evolution API =====
    @app.post("/api/evolution/analyze")
    async def trigger_evolution():
        if harness and harness._evolution:
            result = await harness.trigger_evolution()
            return result
        return {"error": "Evolution not enabled"}
    
    @app.get("/api/evolution/stats")
    async def get_evolution_stats():
        if harness and harness._evolution:
            return harness._evolution.get_stats()
        return {}
    
    # ===== WebSocket =====
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # Echo back for now
                await websocket.send_json({"type": "echo", "data": data})
        except WebSocketDisconnect:
            manager.disconnect(websocket)
    
    # Serve frontend
    @app.get("/")
    async def serve_frontend():
        from fastapi.responses import FileResponse
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend not found"}
    
    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    agent_class=None,
    config: Dict[str, Any] = None,
    reload: bool = False
):
    """Run the web server."""
    app = create_app(agent_class, config)
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()