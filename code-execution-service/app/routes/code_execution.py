from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from datetime import datetime

from ..schemas import (
    CodeSubmissionRequest,
    CodeSubmissionResponse,
    ExecutionStatusResponse,
    ImmediateExecutionResponse,
    ExecutionListSummaryResponse,
    ExecutionSummary,
)
from ..services.code_execution import code_execution_service
from ..services.websocket import websocket_manager
from ..database import redis_manager
from ..config import settings

router = APIRouter()



user = {
    "uid": "1"
}


@router.post("/execute", response_model=CodeSubmissionResponse)
async def submit_code_execution(
    submission: CodeSubmissionRequest,
):
    """Submit code for execution"""
    try:
        execution_id = await code_execution_service.submit_code_execution(
            code=submission.code,
            language=submission.language,
            input_data=submission.input_data,
            user_id=user["uid"],
        )

        return CodeSubmissionResponse(
            execution_id=execution_id,
            status="pending",
            message=f"Code submitted for execution. Use execution_id: {execution_id} to track progress.",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Execution submission failed: {str(e)}"
        )


@router.get("/status/{execution_id}", response_model=ExecutionStatusResponse)
async def get_execution_status(
    execution_id: str,
):
    """Get execution status and results"""

    execution_data = await code_execution_service.get_execution_status(execution_id)

    if not execution_data:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Verify user owns this execution
    if execution_data.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return ExecutionStatusResponse(**execution_data)


@router.post("/webhook/{tmp}")
async def webhook_execution_result(tmp: str, result_data: Dict[str, Any]):
    """Webhook endpoint to receive execution results from third-party API"""

    print(f"Received webhook for execution: {tmp} with data: {result_data}")

    extra_params = result_data.get("extra_params", {})
    if "execution_id" not in extra_params:
        raise HTTPException(
            status_code=400, detail="Missing execution_id in extra_params"
        )
    execution_id = extra_params["execution_id"]
    try:
        # example: {'output': '', 'cpu': '0.05', 'memory': '9400', 'status': 'error', 'error': "line 1, in <module>\n    import pandas as pd\nModuleNotFoundError: No module named 'pandas'\n", 'extra_params': ''}
        # Parse the webhook result
        execution_result = {
            "output": result_data.get("output", ""),
            "error": result_data.get("error", ""),
            "execution_time": result_data.get("cpu", ""),
            "memory_usage": result_data.get("memory", ""),
        }

        # Determine status based on result
        raw_status = result_data.get("status", "").lower()
        
        # Map API status to our internal status
        if raw_status == "success":
            status = "completed"
        elif raw_status == "error":
            status = "error"
        else:
            # For any other status, default to completed if we have output, error if we have error
            if execution_result.get("error"):
                status = "error"
            else:
                status = "completed"
        
        print(f"Webhook processing execution {execution_id}: raw_status={raw_status}, mapped_status={status}, has_output={bool(execution_result.get('output'))}, has_error={bool(execution_result.get('error'))}")

        # Update execution status in Redis
        from ..database import redis_manager

        update_success = await redis_manager.update_execution_status(
            execution_id,
            status,
            output=execution_result.get("output", ""),
            error_output=execution_result.get("error", ""),
            execution_time=execution_result.get("execution_time", ""),
            memory_usage=execution_result.get("memory_usage", ""),
            completed_at=datetime.utcnow().isoformat(),
        )
        
        print(f"Redis update success for execution {execution_id}: {update_success}")

        # Get execution data to find user_id for WebSocket notification
        execution_data = await code_execution_service.get_execution_status(execution_id)
        if execution_data:
            user_id = execution_data.get("user_id")
            if user_id:
                # Send WebSocket update to user
                await websocket_manager.send_execution_update(
                    user_id, execution_id, execution_data
                )

        return {"status": "success", "message": "Execution result received"}

    except Exception as e:
        print(f"Webhook error for execution: {e}")
        # Update status to error
        await redis_manager.update_execution_status(
            execution_id,
            "error",
            error_output=f"Webhook processing error: {str(e)}",
            completed_at=datetime.utcnow().isoformat(),
        )
        raise HTTPException(
            status_code=500, detail=f"Webhook processing failed: {str(e)}"
        )


@router.post("/execute-immediate", response_model=ImmediateExecutionResponse)
async def execute_code_immediate(
    submission: CodeSubmissionRequest,
    timeout: int = Query(default=60, ge=10, le=300, description="Timeout in seconds (10-300)"),
    poll_interval: float = Query(default=1.0, ge=0.5, le=5.0, description="Polling interval in seconds (0.5-5.0)")
):
    """Execute code immediately and wait for result with polling (no webhook required)"""
    try:
        result = await code_execution_service.execute_code_immediate(
            code=submission.code,
            language=submission.language,
            input_data=submission.input_data,
            user_id=user["uid"],
            timeout_seconds=timeout,
            poll_interval=poll_interval
        )

        return ImmediateExecutionResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Immediate execution failed: {str(e)}"
        )


@router.get("/list", response_model=ExecutionListSummaryResponse)
async def list_executions(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of executions to return"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID (admin only in production)")
):
    """List executions from Redis database"""
    try:
        # In production, only allow listing own executions unless admin
        if not settings.debug and user_id and user_id != user["uid"]:
            raise HTTPException(
                status_code=403, 
                detail="Access denied: Cannot view other users' executions in production"
            )
        
        # Get executions
        if user_id:
            executions_data = await redis_manager.list_executions_by_user(user_id, limit)
        else:
            # In production, default to current user's executions
            if not settings.debug:
                executions_data = await redis_manager.list_executions_by_user(user["uid"], limit)
            else:
                executions_data = await redis_manager.list_all_executions(limit)
        
        # Convert to summary format
        executions_summary = []
        for execution in executions_data:
            summary = ExecutionSummary(
                execution_id=execution.get("execution_id", ""),
                user_id=execution.get("user_id", ""),
                language=execution.get("language", ""),
                status=execution.get("status", "unknown"),
                created_at=execution.get("created_at", ""),
                completed_at=execution.get("completed_at"),
                execution_time=execution.get("execution_time"),
                has_output=bool(execution.get("output")),
                has_error=bool(execution.get("error_output"))
            )
            executions_summary.append(summary)

        return ExecutionListSummaryResponse(
            executions=executions_summary,
            total_count=len(executions_summary),
            limit=limit
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list executions: {str(e)}"
        )


@router.get("/list/all", response_model=ExecutionListSummaryResponse)
async def list_all_executions_admin(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of executions to return")
):
    """List all executions (development/admin only)"""
    if not settings.debug:
        raise HTTPException(
            status_code=404, 
            detail="This endpoint is only available in development mode"
        )
    
    try:
        executions_data = await redis_manager.list_all_executions(limit)
        
        # Convert to summary format
        executions_summary = []
        for execution in executions_data:
            summary = ExecutionSummary(
                execution_id=execution.get("execution_id", ""),
                user_id=execution.get("user_id", ""),
                language=execution.get("language", ""),
                status=execution.get("status", "unknown"),
                created_at=execution.get("created_at", ""),
                completed_at=execution.get("completed_at"),
                execution_time=execution.get("execution_time"),
                has_output=bool(execution.get("output")),
                has_error=bool(execution.get("error_output"))
            )
            executions_summary.append(summary)

        return ExecutionListSummaryResponse(
            executions=executions_summary,
            total_count=len(executions_summary),
            limit=limit
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list all executions: {str(e)}"
        )
