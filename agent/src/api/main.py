"""
SRE Agent API v3.0

Production API for Conversational Multi-Agent SRE Workflow.
Uses AutoGen Swarm pattern with dynamic agent participation.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.chat_manager import WebChatManager
from configs.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


# Initialize chat manager for WebSocket (share the same workflow)
chat_manager = WebChatManager()

app = FastAPI(
    title="SRE Agent API",
    description="AutoGen Swarm-based Conversational SRE System for Kubernetes",
    version="3.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info("Static files mounted", directory=str(static_dir))
else:
    logger.warning("Static directory not found", directory=str(static_dir))


@app.get("/")
async def root():
    """Root endpoint - serve UI."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "service": "SRE Agent API",
        "version": "3.0.0",
        "status": "operational",
        "workflow": "Conversational Multi-Agent (Swarm)",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "version": "3.0.0"}


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("SRE Agent API starting")
    # Chat manager uses the shared workflow instance
    logger.info("Chat manager ready with shared workflow")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for chat interface with v6.0 features."""
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            logger.info("WebSocket message received", data=message_data)

            message_type = message_data.get("type")

            # Traditional chat message
            if message_type == "chat":
                user_message = message_data.get("message", "")

                # Extract optional context from message
                context = message_data.get("context", {})
                if "namespace" in message_data:
                    context["namespace"] = message_data["namespace"]
                if "pod" in message_data:
                    context["pod"] = message_data["pod"]

                # Send acknowledgment
                await websocket.send_json(
                    {"type": "status", "message": "Processing your request..."}
                )

                try:
                    # Handle chat message with conversational workflow
                    await chat_manager.handle_chat_message(
                        user_message=user_message, websocket=websocket, context=context
                    )

                except Exception as e:
                    logger.error("Error processing chat", error=str(e))
                    await websocket.send_json(
                        {"type": "error", "message": f"Error: {str(e)}"}
                    )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        try:
            await websocket.close()
        except Exception:
            pass


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("SRE Agent API shutting down")

    try:
        if chat_manager.chat_workflow:
            await chat_manager.chat_workflow.close()
            logger.info("ChatWorkflow closed successfully")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


def run_development():
    """Run development server."""
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


def run_production():
    """Run production server."""
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        log_level="warning",
    )


if __name__ == "__main__":
    run_development()
