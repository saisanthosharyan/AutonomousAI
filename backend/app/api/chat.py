import uuid
from pathlib import Path
from typing import Literal
from app.services.llm.router import LLMRouter

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.orchestrator import AgentOrchestrator
from app.core.logger import logger
from app.database.crud import create_run
from app.database.database import SessionLocal
from app.memory.conversation_cache import (
    add_message,
    get_history,
)

router = APIRouter(tags=["Chat"])


# --------------------------------------------------
# Request Model
# --------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

    provider: Literal[
        "gemini",
        "openai",
        "ollama",
    ] | None = None

    api_key: str | None = Field(
        default=None,
        min_length=1,
    )

    model: str | None = Field(
        default=None,
        min_length=1,
    )


# --------------------------------------------------
# Chat Endpoint
# --------------------------------------------------


@router.post("/chat")
async def chat(request: ChatRequest):

    try:

        logger.info("=" * 60)
        logger.info(f"New chat request received: {request.session_id}")
        logger.info("=" * 60)

        # ------------------------------------------
        # Conversation History
        # ------------------------------------------

        history = get_history(request.session_id)

        add_message(
            request.session_id,
            "user",
            request.message,
        )

        # ------------------------------------------
        # Create Persistent Run
        # ------------------------------------------

        run_id = str(uuid.uuid4())

        db = SessionLocal()

        try:

            create_run(
                db=db,
                run_id=run_id,
                session_id=request.session_id,
                prompt=request.message,
            )

        finally:

            db.close()

        logger.info(f"Created AutoDev-AI run: {run_id}")

        # ------------------------------------------
        # Execute AI Pipeline
        # ------------------------------------------
        llm = LLMRouter.get_llm(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
        )
        orchestrator = AgentOrchestrator(
            llm=llm
        )

        result = await orchestrator.execute(
            task=request.message,
            history=history,
            session_id=request.session_id,
            run_id=run_id,
        )

        # ------------------------------------------
        # Save Assistant Reply
        # ------------------------------------------

        add_message(
            request.session_id,
            "assistant",
            result.get("review", ""),
        )

        # ------------------------------------------
        # Download URL
        # ------------------------------------------

        project = result.get("project", {})

        download_url = None

        if (
            isinstance(project, dict)
            and project.get("project_path")
        ):

            download_url = (
                f"/download/{Path(project['project_path']).name}"
            )

        logger.info(
            f"Chat request completed successfully: {run_id}"
        )

        # ------------------------------------------
        # Response
        # ------------------------------------------

        return {
            "success": result.get("success", False),
            "session_id": request.session_id,
            "run_id": run_id,
            "history": get_history(request.session_id),
            "plan": result.get("plan"),
            "project": {
                **project,
                "download_url": download_url,
            },
            "execution": result.get("execution"),
            "validation": result.get("validation"),
            "tests": result.get("tests"),
            "debug_report": result.get("debug_report"),
            "retry_stats": result.get("retry_stats"),
            "review": result.get("review"),
            "evaluation": result.get("evaluation"),
            "improved_code": result.get("improved_code"),
            "metrics": result.get("metrics"),
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception("Chat endpoint failed.")

        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": str(e),
            },
        )