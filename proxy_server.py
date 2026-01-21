#!/usr/bin/env python3
"""
OpenAI API Compatible Proxy Server
Supports both OpenAI and Azure OpenAI clients with unified API interface
Includes support for Azure Identity (DefaultAzureCredential)
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import openai
from openai import AsyncOpenAI, AsyncAzureOpenAI
from openai import APIError, RateLimitError, AuthenticationError

# Azure Identity support
try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenAI API Proxy", version="1.1.0")

# Configuration models
class OpenAIConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    organization: Optional[str] = None

class AzureOpenAIConfig(BaseModel):
    api_key: Optional[str] = None
    api_version: str = "2024-02-15-preview"
    azure_endpoint: str
    azure_deployment: str
    use_azure_identity: bool = False

class ProxyConfig(BaseModel):
    openai: Optional[OpenAIConfig] = None
    azure_openai: Optional[AzureOpenAIConfig] = None
    master_key: str = "sk-1234"
    port: int = 4000
    host: str = "0.0.0.0"

# Request models (OpenAI compatible)
class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

class CompletionRequest(BaseModel):
    model: str
    prompt: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None

class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]

# Global clients
openai_client: Optional[AsyncOpenAI] = None
azure_client: Optional[AsyncAzureOpenAI] = None
config: ProxyConfig = None

def load_config() -> ProxyConfig:
    """Load configuration from environment variables"""
    # Check for Azure Identity requirement
    use_azure_ad = os.getenv("AZURE_AD_TOKEN") is not None or os.getenv("USE_AZURE_IDENTITY", "false").lower() == "true"
    
    return ProxyConfig(
        openai=OpenAIConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            organization=os.getenv("OPENAI_ORGANIZATION")
        ) if os.getenv("OPENAI_API_KEY") else None,
        azure_openai=AzureOpenAIConfig(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
            azure_deployment=os.getenv("AZURE_DEPLOYMENT"),
            use_azure_identity=use_azure_ad
        ) if (os.getenv("AZURE_OPENAI_API_KEY") or use_azure_ad) and os.getenv("AZURE_ENDPOINT") else None,
        master_key=os.getenv("MASTER_KEY", "sk-1234"),
        port=int(os.getenv("PORT", "4000")),
        host=os.getenv("HOST", "0.0.0.0")
    )

def initialize_clients():
    """Initialize Async OpenAI and Azure OpenAI clients"""
    global openai_client, azure_client, config
    
    config = load_config()
    
    if config.openai:
        openai_client = AsyncOpenAI(
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            organization=config.openai.organization
        )
        logger.info("Async OpenAI client initialized")
    
    if config.azure_openai:
        if config.azure_openai.use_azure_identity and AZURE_IDENTITY_AVAILABLE:
            # Use DefaultAzureCredential
            logger.info("Using Azure Identity (DefaultAzureCredential) for authentication")
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            
            azure_client = AsyncAzureOpenAI(
                azure_ad_token_provider=token_provider,
                api_version=config.azure_openai.api_version,
                azure_endpoint=config.azure_openai.azure_endpoint,
                azure_deployment=config.azure_openai.azure_deployment
            )
        else:
            # Use API Key
            if not config.azure_openai.api_key:
                logger.warning("Azure OpenAI API key missing and Azure Identity not enabled/available")
            
            azure_client = AsyncAzureOpenAI(
                api_key=config.azure_openai.api_key,
                api_version=config.azure_openai.api_version,
                azure_endpoint=config.azure_openai.azure_endpoint,
                azure_deployment=config.azure_openai.azure_deployment
            )
        logger.info("Async Azure OpenAI client initialized")

def authenticate_request(request: Request):
    """Validate master key authentication"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    if token != config.master_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True

def get_client(model: str):
    """Determine which client to use based on model name"""
    # Simple routing logic - can be enhanced with a map
    if model.startswith("gpt-") and openai_client:
        return openai_client
    elif (model.startswith("azure-") or "gpt" in model) and azure_client:
        return azure_client
    elif azure_client:
        return azure_client  # Default to Azure if available
    elif openai_client:
        return openai_client  # Default to OpenAI if available
    else:
        raise HTTPException(status_code=400, detail="No configured AI providers")

@app.get("/health/readiness")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Proxy is ready"}

@app.get("/models")
async def list_models(auth: bool = Depends(authenticate_request)):
    """List available models (OpenAI compatible)"""
    models = []
    
    if openai_client:
        models.extend([
            {"id": "gpt-4o", "object": "model", "owned_by": "openai"},
            {"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"},
            {"id": "gpt-4-turbo", "object": "model", "owned_by": "openai"}
        ])
    
    if azure_client:
        models.extend([
            {"id": "azure-gpt-4", "object": "model", "owned_by": "azure"},
            {"id": "azure-gpt-4-turbo", "object": "model", "owned_by": "azure"},
            {"id": "azure-gpt-35-turbo", "object": "model", "owned_by": "azure"}
        ])
    
    return {"object": "list", "data": models}

@app.post("/chat/completions")
async def chat_completion(request: ChatCompletionRequest, auth: bool = Depends(authenticate_request)):
    """Chat completion endpoint (OpenAI compatible)"""
    try:
        client = get_client(request.model)
        
        response = await client.chat.completions.create(
            model=request.model,
            messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream
        )
        
        if request.stream:
            # Handle streaming response
            async def generate():
                try:
                    async for chunk in response:
                        yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    # Cannot send HTTP error code here as headers already sent
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            # Normal response
            return response.model_dump()
            
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(status_code=429, detail="Upstream rate limit exceeded")
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Upstream authentication failed")
    except APIError as e:
        logger.error(f"Upstream API error: {e}")
        status_code = getattr(e, "status_code", 502) or 502
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/completions")
async def completion(request: CompletionRequest, auth: bool = Depends(authenticate_request)):
    """Text completion endpoint (OpenAI compatible)"""
    try:
        client = get_client(request.model)
        
        response = await client.completions.create(
            model=request.model,
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return response.model_dump()
        
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        raise HTTPException(status_code=429, detail="Upstream rate limit exceeded")
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Upstream authentication failed")
    except APIError as e:
        logger.error(f"Upstream API error: {e}")
        status_code = getattr(e, "status_code", 502) or 502
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/embeddings")
# async def embeddings(request: EmbeddingRequest, auth: bool = Depends(authenticate_request)):
#     """Embeddings endpoint (OpenAI compatible) - Temporarily disabled"""
#     try:
#         client = get_client(request.model)
#         
#         response = await client.embeddings.create(
#             model=request.model,
#             input=request.input
#         )
#         
#         return response.model_dump()
#         
#     except RateLimitError as e:
#         logger.warning(f"Rate limit exceeded: {e}")
#         raise HTTPException(status_code=429, detail="Upstream rate limit exceeded")
#     except AuthenticationError as e:
#         logger.error(f"Authentication error: {e}")
#         raise HTTPException(status_code=401, detail="Upstream authentication failed")
#     except APIError as e:
#         logger.error(f"Upstream API error: {e}")
#         status_code = getattr(e, "status_code", 502) or 502
#         raise HTTPException(status_code=status_code, detail=str(e))
#     except Exception as e:
#         logger.error(f"Embeddings error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "OpenAI API Proxy",
        "version": "1.1.0",
        "features": ["async", "azure-identity"],
        "endpoints": {
            "chat_completions": "/chat/completions",
            "completions": "/completions", 
            "embeddings": "/embeddings",
            "models": "/models",
            "health": "/health/readiness"
        },
        "supported_providers": {
            "openai": bool(config.openai),
            "azure_openai": bool(config.azure_openai),
            "azure_identity_enabled": config.azure_openai.use_azure_identity if config.azure_openai else False
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # Initialize clients
    initialize_clients()
    
    if not openai_client and not azure_client:
        logger.error("No AI providers configured. Please set environment variables.")
        exit(1)
    
    # Start server
    logger.info(f"Starting OpenAI API proxy on {config.host}:{config.port}")
    uvicorn.run(app, host=config.host, port=config.port)