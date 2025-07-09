import httpx
import json
import uuid
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
                
                print(f"Submitting code execution request: {body}")
                result = response.text.strip()
                print(f"API response: {result}")
                
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
