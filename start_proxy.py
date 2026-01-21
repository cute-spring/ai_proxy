#!/usr/bin/env python3
"""
Startup script for OpenAI API Proxy
Handles environment setup and server initialization
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if required environment variables are set"""
    required_vars = []
    
    # Load env vars
    openai_key = os.getenv("OPENAI_API_KEY")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_ENDPOINT")
    
    # Check for Azure Identity usage
    use_azure_identity = os.getenv("USE_AZURE_IDENTITY", "false").lower() == "true"
    azure_ad_token = os.getenv("AZURE_AD_TOKEN")
    
    has_openai = bool(openai_key)
    has_azure = bool(azure_endpoint and (azure_key or use_azure_identity or azure_ad_token))
    
    if not has_openai and not has_azure:
        logger.error("No AI providers configured. Please set either:")
        logger.error("  - OPENAI_API_KEY for OpenAI")
        logger.error("  - AZURE_ENDPOINT + AZURE_OPENAI_API_KEY for Azure OpenAI")
        logger.error("  - AZURE_ENDPOINT + USE_AZURE_IDENTITY=true for Azure Managed Identity")
        return False
    
    if has_openai:
        logger.info("✅ OpenAI provider configured")
    
    if has_azure:
        if use_azure_identity:
            logger.info("✅ Azure OpenAI provider configured (using Azure Identity)")
        elif azure_ad_token:
            logger.info("✅ Azure OpenAI provider configured (using AD Token)")
        else:
            logger.info("✅ Azure OpenAI provider configured (using API Key)")
            
    if azure_key and not azure_endpoint:
        logger.warning("⚠️  AZURE_OPENAI_API_KEY set but AZURE_ENDPOINT missing")
    
    # Check master key
    master_key = os.getenv("MASTER_KEY", "sk-1234")
    if master_key == "sk-1234":
        logger.warning("⚠️  Using default master key. Set MASTER_KEY environment variable for production.")
    
    return True

def main():
    """Main startup function"""
    
    # Load environment variables from .env file
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from {env_path}")
    else:
        logger.info("No .env file found, using system environment variables")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Import and start the server
    try:
        from proxy_server import app, initialize_clients
        import uvicorn
        
        # Initialize clients
        initialize_clients()
        
        # Get configuration
        port = int(os.getenv("PORT", "4000"))
        host = os.getenv("HOST", "0.0.0.0")
        
        logger.info(f"Starting OpenAI API Proxy on {host}:{port}")
        logger.info("Available endpoints:")
        logger.info("  - GET  /health/readiness")
        logger.info("  - GET  /models") 
        logger.info("  - POST /chat/completions")
        logger.info("  - POST /completions")
        logger.info("  - POST /embeddings")
        
        # Start server
        uvicorn.run(app, host=host, port=port, log_level="info")
        
    except ImportError as e:
        logger.error(f"Failed to import dependencies: {e}")
        logger.error("Please install requirements: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()