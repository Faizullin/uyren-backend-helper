import httpx
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any

from ..config import settings
from ..database import redis_manager


class CodeExecutionService:
    """Service for executing code using third-party API"""
    
    def __init__(self):
        self.api_url = settings.code_execution_api_url
        self.api_key = settings.code_execution_api_key
        self.headers = {
            "Accept": "*/*",
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def submit_code_execution(
        self, 
        code: str, 
        language: str, 
        input_data: str, 
        user_id: str
    ) -> str:
        """Submit code for execution and return execution_id"""
        
        execution_id = str(uuid.uuid4())
        
        # Store initial execution data in Redis
        execution_data = {
            "execution_id": execution_id,
            "user_id": user_id,
            "code": code,
            "language": language,
            "input_data": input_data,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "output": None,
            "error_output": None,
            "execution_time": None,
            "memory_usage": None
        }
        
        await redis_manager.set_execution_data(execution_id, execution_data)
        
        # Execute code asynchronously        
        await self._execute_code_async(execution_id, code, language, input_data)
        
        return execution_id
    
    async def execute_code_immediate(
        self, 
        code: str, 
        language: str, 
        input_data: str, 
        user_id: str,
        timeout_seconds: int = 30,
        poll_interval: float = 1.0
    ) -> Dict[str, Any]:
        """Execute code and wait for result with polling (no webhook)"""
        
        execution_id = str(uuid.uuid4())
        
        # Store initial execution data in Redis
        execution_data = {
            "execution_id": execution_id,
            "user_id": user_id,
            "code": code,
            "language": language,
            "input_data": input_data,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "output": None,
            "error_output": None,
            "execution_time": None,
            "memory_usage": None
        }
        
        await redis_manager.set_execution_data(execution_id, execution_data)
        
        try:
            # Submit code for execution
            await self._execute_code_async(execution_id, code, language, input_data)
            
            # Small delay to allow immediate processing
            await asyncio.sleep(0.5)
            
            # Poll for results
            start_time = datetime.utcnow()
            last_status = None
            poll_count = 0
            
            while True:
                poll_count += 1
                
                # Check if timeout exceeded
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                print(f"Polling execution {execution_id} (poll #{poll_count}, elapsed={elapsed:.1f}s)")
                if elapsed >= timeout_seconds:
                    # Before timing out, check one more time
                    final_data = await redis_manager.get_execution_data(execution_id)
                    if final_data and final_data.get("status") in ["completed", "error"]:
                        status = final_data.get("status")
                        return {
                            "execution_id": execution_id,
                            "status": status,
                            "output": final_data.get("output"),
                            "error_output": final_data.get("error_output"),
                            "execution_time": final_data.get("execution_time"),
                            "memory_usage": final_data.get("memory_usage"),
                            "message": "Execution completed" if status == "completed" else "Execution failed"
                        }
                    
                    return {
                        "execution_id": execution_id,
                        "status": "timeout",
                        "output": None,
                        "error_output": None,
                        "execution_time": None,
                        "memory_usage": None,
                        "message": f"Execution timed out after {timeout_seconds} seconds. Last status: {last_status}"
                    }
                
                # Get current execution status
                current_data = await redis_manager.get_execution_data(execution_id)
                if not current_data:
                    return {
                        "execution_id": execution_id,
                        "status": "error",
                        "output": None,
                        "error_output": "Execution data not found",
                        "execution_time": None,
                        "memory_usage": None,
                        "message": "Execution data was lost or expired"
                    }
                
                status = current_data.get("status", "pending")
                
                # Track status changes
                if status != last_status:
                    print(f"Execution {execution_id} status changed: {last_status} -> {status} (poll #{poll_count}, elapsed={elapsed:.1f}s)")
                    last_status = status
                
                # Check if execution is complete - handle both our mapped statuses and raw API statuses
                if status in ["completed", "error", "success"]:
                    # Map success to completed for consistency
                    final_status = "completed" if status == "success" else status
                    return {
                        "execution_id": execution_id,
                        "status": final_status,
                        "output": current_data.get("output"),
                        "error_output": current_data.get("error_output"),
                        "execution_time": current_data.get("execution_time"),
                        "memory_usage": current_data.get("memory_usage"),
                        "message": "Execution completed" if final_status == "completed" else "Execution failed"
                    }
                
                # Adaptive polling: shorter interval for first few polls, then longer
                if poll_count <= 5:
                    current_interval = min(poll_interval, 0.5)  # Fast polling initially
                elif status == "waiting":
                    current_interval = poll_interval  # Normal polling for waiting
                else:
                    current_interval = min(poll_interval * 1.5, 3.0)  # Slower for other statuses
                
                # Wait before next poll
                await asyncio.sleep(current_interval)
                
        except Exception as e:
            return {
                "execution_id": execution_id,
                "status": "error",
                "output": None,
                "error_output": str(e),
                "execution_time": None,
                "memory_usage": None,
                "message": f"Execution failed: {str(e)}"
            }
    
    async def _execute_code_async(self, execution_id: str, code: str, language: str, input_data: str):
        """Execute code asynchronously"""
        try:
            # Update status to running
            await redis_manager.update_execution_status(execution_id, "running")
            
            # Prepare request body based on third-party API requirements
            body = {
                "code": code,
                "input": input_data,
                "compiler": self._get_compiler_name(language),
                "extra_params": {
                    "execution_id": execution_id,
                }
            }
            
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    data=json.dumps(body)
                )
                response.raise_for_status()
                result = response.text.strip()
                
                # Check if response is simple "Ok" confirmation
                if result.lower() in ["ok", "success", "submitted"]:
                    # Update status to waiting for webhook
                    await redis_manager.update_execution_status(
                        execution_id, 
                        "waiting",
                        message="Code submitted successfully. Waiting for execution results via webhook."
                    )
                    print(f"Execution {execution_id} submitted successfully. Status set to 'waiting' for webhook updates.")
                else:
                    # If we get actual execution results immediately, parse them
                    try:
                        execution_result = self._parse_execution_result(json.loads(result))
                        await redis_manager.update_execution_status(
                            execution_id, 
                            "completed",
                            output=execution_result.get("output", ""),
                            error_output=execution_result.get("error", ""),
                            execution_time=execution_result.get("execution_time", ""),
                            memory_usage=execution_result.get("memory_usage", ""),
                            completed_at=datetime.utcnow().isoformat()
                        )
                    except json.JSONDecodeError:
                        # If it's not JSON, treat as plain text output
                        await redis_manager.update_execution_status(
                            execution_id, 
                            "completed",
                            output=result,
                            completed_at=datetime.utcnow().isoformat()
                        )
                
        except Exception as e:
            # Update status to error
            await redis_manager.update_execution_status(
                execution_id, 
                "error",
                error_output=str(e),
                completed_at=datetime.utcnow().isoformat()
            )
        except Exception as e:
            # Update status to error
            await redis_manager.update_execution_status(
                execution_id, 
                "error",
                error_output=str(e),
                completed_at=datetime.utcnow().isoformat()
            )
    
    def _get_compiler_name(self, language: str) -> str:
        """Map language to compiler name for third-party API"""
        language_map = {
            "python": "python-3.9.7",
            "python3": "python-3.9.7",
            "python2": "python-2.7.18",
            "c": "gcc-4.9",
            "cpp": "g++-4.9",
            "c++": "g++-4.9",
            "java": "openjdk-11",
            "csharp": "dotnet-csharp-5",
            "c#": "dotnet-csharp-5",
            "fsharp": "dotnet-fsharp-5",
            "f#": "dotnet-fsharp-5",
            "php": "php-8.1",
            "ruby": "ruby-3.0.2",
            "haskell": "haskell-9.2.7"
        }
        
        compiler = language_map.get(language.lower())
        if not compiler:
            supported_languages = ", ".join(sorted(language_map.keys()))
            raise ValueError(
                f"Unsupported language: '{language}'. "
                f"Supported languages: {supported_languages}"
            )
        
        return compiler
    
    def _parse_execution_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the execution result from third-party API"""
        return {
            "output": result.get("output", ""),
            "error": result.get("error", ""),
            "execution_time": result.get("cpuTime", ""),
            "memory_usage": result.get("memory", "")
        }
    
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status and results"""
        return await redis_manager.get_execution_data(execution_id)


# Global code execution service instance
code_execution_service = CodeExecutionService()
