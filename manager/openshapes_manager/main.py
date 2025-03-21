from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
import json
import os
import sys
import logging, secrets
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from bson.objectid import ObjectId
import dotenv
from datetime import datetime, timedelta
import secrets, psutil
import jwt
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from models import *

# Ensure the openshapes_manager module is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import OpenShapesManager (ensure it's in the Python path)
from openshapes_manager.bot import OpenShapesManager
from openshapes_manager.container import ContainerManager

import nest_asyncio
nest_asyncio.apply()
# Load environment variables
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# Initialize FastAPI app
app = FastAPI(title="OpenShapes Manager API", docs_url=None, redoc_url=None)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Discord OAuth2 setup
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:3000/api/auth/callback/discord")
DISCORD_API_ENDPOINT = "https://discord.com/api"
# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 24 * 60 * 60  # 24 hours in seconds

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
db = client["openshapes"]
users_collection = db["users"]
bots_collection = db["bots"]

# Initialize OpenShapesManager
bot_manager = OpenShapesManager()

if bot_manager.config is None:
    logger.warning("Bot manager has no configuration, creating default")
    bot_manager.config = {
        "data_dir": "openshapes_data",
        "max_bots_per_user": 5, 
        "admin_users": [],
        "admin_roles": [],
        "docker_base_image": "openshapes:latest"
    }
    bot_manager.save_config()

# Make sure the directories exist
if "data_dir" in bot_manager.config:
    from openshapes_manager.utils import create_required_directories
    create_required_directories(bot_manager.config["data_dir"])

if not hasattr(bot_manager, 'container_manager') or bot_manager.container_manager is None:
    logger.info("Initializing container manager")
    bot_manager.container_manager = ContainerManager(bot_manager.logger, bot_manager.config)
    
# Security utilities
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION)
    to_encode.update({"exp": expire})
    print(to_encode)
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def get_current_user(request: Request) -> User:
    token = None
    
    # Check for token in Authorization header
    if "Authorization" in request.headers:
        auth = request.headers["Authorization"]
        scheme, token = auth.split()
        if scheme.lower() != "bearer":
            token = None
    
    # Check for token in cookies
    if not token and "access_token" in request.cookies:
        token = request.cookies["access_token"]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = users_collection.find_one({"id": user_id})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Convert ObjectId to str for serialization
    if "_id" in user:
        user["_id"] = str(user["_id"])
    
    return User(**user)

@app.get("/")
async def read_root():
    return {"message": "OpenShapes Manager API"}

# Authentication routes
@app.get("/api/auth/discord")
async def auth_discord():
    """Redirect to Discord OAuth2 authorization page"""
    discord_auth_url = (
        f"{DISCORD_API_ENDPOINT}/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
    )
    return RedirectResponse(url=discord_auth_url)


@app.get("/api/auth/callback")
async def auth_callback(code: str):
    """Handle Discord OAuth2 callback and exchange code for token"""
    # Exchange code for token
    token_url = f"{DISCORD_API_ENDPOINT}/oauth2/token"
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    print(data)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data, headers=headers)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get Discord token",
            )
        
        token_data = response.json()
        
        # Get user info from Discord
        user_url = f"{DISCORD_API_ENDPOINT}/users/@me"
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        user_response = await client.get(user_url, headers=headers)
        
        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user data from Discord",
            )
        
        discord_user = user_response.json()
        
        # Check if user exists in database, create if not
        user = users_collection.find_one({"id": discord_user["id"]})
        
        if not user:
            new_user = {
                "id": discord_user["id"],
                "username": discord_user["username"],
                "discriminator": discord_user.get("discriminator", "0"),
                "avatar": discord_user.get("avatar"),
                "bot_credits": 3,
                "is_admin": False,  # Default to non-admin
                "created_at": datetime.utcnow(),
                "last_login": datetime.utcnow(),
            }
            users_collection.insert_one(new_user)
            user = new_user
        else:
            # Update last login time
            users_collection.update_one(
                {"id": discord_user["id"]},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            
            # Update other user details if they've changed
            users_collection.update_one(
                {"id": discord_user["id"]},
                {"$set": {
                    "username": discord_user["username"],
                    "discriminator": discord_user.get("discriminator", "0"),
                    "avatar": discord_user.get("avatar"),
                }}
            )
    
    # Create JWT token
    access_token = create_access_token({"sub": discord_user["id"]})
    
    # Redirect to frontend with token
    redirect_url = f"{os.getenv('FRONTEND_URL', 'http://127.0.0.1:7000')}?token={access_token}"
    response = RedirectResponse(url=redirect_url)
    
    # Set cookie with token
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        max_age=JWT_EXPIRATION,
    )
    
    return response


@app.get("/api/auth/logout")
async def logout():
    """Logout by clearing the cookie"""
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="access_token")
    return response


# User management routes
@app.get("/api/user", response_model=UserOut)
async def get_current_user_route(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user"""
    return current_user


# Bot management routes
@app.get("/api/bots")
async def get_user_bots(current_user: User = Depends(get_current_user)):
    """Get all bots owned by the current user"""
    # Refresh bot list to ensure we have up-to-date information
    await bot_manager.refresh_bot_list()
    
    # Get bots from the database
    db_bots = list(bots_collection.find({"owner_id": current_user.id}))
    
    # Convert MongoDB ObjectIDs to strings
    for bot in db_bots:
        bot["_id"] = str(bot["_id"])
    
    # Get real-time status from container manager
    user_bots = bot_manager.get_user_bots(current_user.id)
    
    # Combine database information with real-time status
    result = []
    for bot in db_bots:
        bot_entry = {
            "id": bot["_id"],
            "name": bot["name"],
            "owner_id": bot["owner_id"],
            "description": bot.get("description", ""),
            "created_at": bot.get("created_at", datetime.utcnow()),
            "status": "stopped"
        }
        
        # Update with real-time status if available
        if bot["name"] in user_bots:
            bot_entry["status"] = user_bots[bot["name"]]["status"]
            bot_entry["container_id"] = user_bots[bot["name"]]["container_id"]
        
        result.append(bot_entry)
    
    return {"bots": result}


@app.post("/api/bots/import")
async def import_bot(bot_data: BotCreate, current_user: User = Depends(get_current_user)):
    """Create a new bot"""
    # Check if user has enough credits
    if current_user.bot_credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Not enough bot credits"
        )
    
    # Check if bot name is available
    existing_bot = bots_collection.find_one({
        "owner_id": current_user.id,
        "name": bot_data.name
    })
    
    if existing_bot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a bot named {bot_data.name}"
        )
    
    # Create bot configuration JSON
    config_json = json.dumps(bot_data.config)
    brain_json = None
    if bot_data.brain_data:
        brain_json = json.dumps(bot_data.brain_data)
    
    # Create the bot using OpenShapesManager
    success, message = await bot_manager.create_bot(
        current_user.id,
        bot_data.name,
        config_json,
        bot_data.bot_token,
        brain_json
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    # Store bot information in database
    bot_document = {
        "name": bot_data.name,
        "owner_id": current_user.id,
        "description": bot_data.description or "",
        "created_at": datetime.utcnow(),
    }
    
    result = bots_collection.insert_one(bot_document)
    
    # Deduct a credit from the user
    users_collection.update_one(
        {"id": current_user.id},
        {"$inc": {"bot_credits": -1}}
    )
    
    return {
        "id": str(result.inserted_id),
        "message": message
    }

@app.post("/api/bots")
async def create_bot(bot_data: DirectBotCreate, current_user: User = Depends(get_current_user)):
    """Create a new bot directly with parameters"""
    # Check if user has enough credits
    if current_user.bot_credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Not enough bot credits"
        )
        
    bot_name = bot_data.character_name.lower().replace(" ", "_")
    
    # Check if bot name is available
    existing_bot = bots_collection.find_one({
        "owner_id": current_user.id,
        "name": bot_name
    })
    
    
    # Append random hex to bot name if it already exists
    if existing_bot:
        bot_name = f"{bot_name}_{secrets.token_hex(4)}"
        existing_bot = bots_collection.find_one({
            "owner_id": current_user.id,
            "name": bot_name
        })
    
    if existing_bot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a bot named {bot_name}"
        )
    
    # Build config directly from parameters
    config = {
        "bot_token": bot_data.bot_token,
        "owner_id": current_user.id,
        "character_name": bot_data.character_name,
        "allowed_guilds": [],
        "command_prefix": "!",
        "system_prompt": bot_data.system_prompt,
        "character_backstory": bot_data.character_backstory,
        "character_description": bot_data.character_description,
        "personality_catchphrases": bot_data.personality_catchphrases,
        "personality_age": bot_data.personality_age,
        "personality_likes": bot_data.personality_likes,
        "personality_dislikes": bot_data.personality_dislikes,
        "personality_goals": bot_data.personality_goals,
        "personality_traits": bot_data.personality_traits,
        "personality_physical_traits": bot_data.personality_physical_traits,
        "personality_tone": bot_data.personality_tone,
        "personality_history": bot_data.personality_history,
        "personality_conversational_goals": bot_data.personality_conversational_goals.replace("{user}", "[user]") if bot_data.personality_conversational_goals else "",
        "personality_conversational_examples": bot_data.personality_conversational_examples.replace("{user}", "[user]") if bot_data.personality_conversational_examples else "",
        "character_scenario": bot_data.character_scenario,
        "free_will": bot_data.free_will,
        "free_will_instruction": bot_data.free_will_instruction,
        "jailbreak": bot_data.jailbreak,
        "add_character_name": bot_data.add_character_name,
        "reply_to_name": bot_data.reply_to_name,
        "always_reply_mentions": bot_data.always_reply_mentions,
        "use_tts": bot_data.use_tts,
        "data_dir": "character_data",
        "api_settings": {
            "base_url": bot_data.api_base_url,
            "api_key": bot_data.api_key,
            "chat_model": bot_data.chat_model,
            "tts_model": bot_data.tts_model,
            "tts_voice": bot_data.tts_voice,
        },
        "activated_channels": [],
        "blacklisted_users": [],
        "blacklisted_roles": [],
        "conversation_timeout": 30,
    }
    
    # Create bot config directory and save config.json
    bot_dir = bot_manager.get_bot_config_dir(current_user.id, bot_name)
    config_path = os.path.join(bot_dir, "character_config.json")
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    # Start the bot
    container_result = await bot_manager.container_manager.start_bot_container(
        current_user.id, bot_name, bot_dir
    )
    
    if not container_result[0]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=container_result[1]
        )
    
    await bot_manager.container_manager.refresh_bot_list()
    
    # Store bot information in database
    bot_document = {
        "name": bot_name,
        "owner_id": current_user.id,
        "description": f"AI Character: {bot_data.character_name}",
        "created_at": datetime.utcnow(),
    }
    
    result = bots_collection.insert_one(bot_document)
    
    # Deduct a credit from the user
    users_collection.update_one(
        {"id": current_user.id},
        {"$inc": {"bot_credits": -1}}
    )
    
    return {
        "id": str(result.inserted_id),
        "message": f"Bot {bot_name} created and started successfully"
    }

@app.get("/api/bots/{bot_id}")
async def get_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    """Get details for a specific bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this bot"
        )
    
    # Convert MongoDB ObjectID to string
    bot["_id"] = str(bot["_id"])
    
    # Get real-time status
    user_bots = bot_manager.get_user_bots(current_user.id)
    if bot["name"] in user_bots:
        bot["status"] = user_bots[bot["name"]]["status"]
        bot["container_id"] = user_bots[bot["name"]]["container_id"]
    else:
        bot["status"] = "stopped"
    
    # Get configuration if possible
    try:
        bot_dir = bot_manager.get_bot_config_dir(current_user.id, bot["name"])
        config_path = os.path.join(bot_dir, "character_config.json")
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                bot["config"] = json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        bot["config"] = {"error": "Could not load configuration"}
    
    return bot


@app.put("/api/bots/{bot_id}")
async def update_bot(
    bot_id: str, 
    bot_data: BotUpdate, 
    current_user: User = Depends(get_current_user)
):
    """Update a bot's details"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this bot"
        )
    
    # Prepare update document
    update_data = {}
    
    if bot_data.name is not None:
        # Check if the new name is available
        if bot_data.name != bot["name"]:
            existing_bot = bots_collection.find_one({
                "owner_id": current_user.id,
                "name": bot_data.name
            })
            
            if existing_bot:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"You already have a bot named {bot_data.name}"
                )
            
            update_data["name"] = bot_data.name
    
    if bot_data.description is not None:
        update_data["description"] = bot_data.description
    
    # Update configuration if provided
    if bot_data.config is not None:
        try:
            bot_dir = bot_manager.get_bot_config_dir(current_user.id, bot["name"])
            config_path = os.path.join(bot_dir, "character_config.json")
            
            if os.path.exists(config_path):
                # Read existing config
                with open(config_path, "r") as f:
                    current_config = json.load(f)
                
                # Update with new config
                current_config.update(bot_data.config)
                
                # Write back
                with open(config_path, "w") as f:
                    json.dump(current_config, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update configuration: {str(e)}"
            )
    
    # Update database if we have any changes
    if update_data:
        bots_collection.update_one(
            {"_id": ObjectId(bot_id)},
            {"$set": update_data}
        )
    
    return {"message": "Bot updated successfully"}


@app.delete("/api/bots/{bot_id}")
async def delete_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    """Delete a bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this bot"
        )
    
    # Delete the bot
    success, message = await bot_manager.delete_bot(current_user.id, bot["name"])
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    # Remove from database
    bots_collection.delete_one({"_id": ObjectId(bot_id)})
    
    # Refund a credit to the user
    users_collection.update_one(
        {"id": current_user.id},
        {"$inc": {"bot_credits": 1}}
    )
    
    return {"message": "Bot deleted successfully and credit refunded"}


@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    """Start a bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control this bot"
        )
    
    # Start the bot
    success, message = await bot_manager.start_bot(current_user.id, bot["name"])
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    return {"message": message}


@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    """Stop a bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control this bot"
        )
    
    # Stop the bot
    success, message = await bot_manager.stop_bot(current_user.id, bot["name"])
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    return {"message": message}


@app.post("/api/bots/{bot_id}/restart")
async def restart_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    """Restart a bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control this bot"
        )
    
    # Restart the bot
    success, message = await bot_manager.restart_bot(current_user.id, bot["name"])
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    return {"message": message}


@app.get("/api/bots/{bot_id}/logs")
async def get_bot_logs(
    bot_id: str, 
    lines: int = 50, 
    current_user: User = Depends(get_current_user)
):
    """Get logs for a bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this bot's logs"
        )
    
    # Get logs
    success, logs = await bot_manager.get_bot_logs(current_user.id, bot["name"], lines)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=logs
        )
    
    return {"logs": logs}


@app.get("/api/bots/{bot_id}/stats")
async def get_bot_stats(bot_id: str, current_user: User = Depends(get_current_user)):
    """Get statistics for a bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this bot's stats"
        )
    
    # Get stats
    success, stats = await bot_manager.get_bot_stats(current_user.id, bot["name"])
    
    if not success or not stats:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve stats"
        )
    
    return {"stats": stats}


@app.put("/api/bots/{bot_id}/api-settings")
async def update_api_settings(
    bot_id: str, 
    settings: APISettingsUpdate, 
    current_user: User = Depends(get_current_user)
):
    """Update API settings for a bot"""
    try:
        bot = bots_collection.find_one({"_id": ObjectId(bot_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot ID format"
        )
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this bot"
        )
    
    try:
        bot_dir = bot_manager.get_bot_config_dir(current_user.id, bot["name"])
        config_path = os.path.join(bot_dir, "character_config.json")
        
        if os.path.exists(config_path):
            # Read existing config
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Ensure api_settings exists
            if "api_settings" not in config:
                config["api_settings"] = {}
            
            # Update settings
            if settings.base_url is not None:
                config["api_settings"]["base_url"] = settings.base_url
            
            if settings.api_key is not None:
                config["api_settings"]["api_key"] = settings.api_key
            
            if settings.chat_model is not None:
                config["api_settings"]["chat_model"] = settings.chat_model
            
            if settings.tts_model is not None:
                config["api_settings"]["tts_model"] = settings.tts_model
            
            if settings.tts_voice is not None:
                config["api_settings"]["tts_voice"] = settings.tts_voice
            
            # Write back
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            # Restart the bot to apply settings if it's running
            user_bots = bot_manager.get_user_bots(current_user.id)
            if bot["name"] in user_bots and user_bots[bot["name"]]["status"] == "running":
                await bot_manager.restart_bot(current_user.id, bot["name"])
            
            return {"message": "API settings updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot configuration file not found"
            )
    except Exception as e:
        logger.error(f"Error updating API settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update API settings: {str(e)}"
        )


# Admin routes (only accessible by admins)
@app.get("/api/admin/users")
async def get_all_users(current_user: User = Depends(get_current_user)):
    """Get all users (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    users = list(users_collection.find())
    
    # Convert MongoDB ObjectIDs to strings
    for user in users:
        if "_id" in user:
            user["_id"] = str(user["_id"])
    
    return {"users": users}


@app.post("/api/admin/users/{user_id}/credits")
async def add_user_credits(
    user_id: str, 
    credits: int = 1, 
    current_user: User = Depends(get_current_user)
):
    """Add credits to a user (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    result = users_collection.update_one(
        {"id": user_id},
        {"$inc": {"bot_credits": credits}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": f"Added {credits} credits to user {user_id}"}


@app.post("/api/admin/users/{user_id}/admin")
async def set_admin_status(
    user_id: str, 
    is_admin: bool, 
    current_user: User = Depends(get_current_user)
):
    """Set admin status for a user (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    result = users_collection.update_one(
        {"id": user_id},
        {"$set": {"is_admin": is_admin}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": f"User {user_id} admin status set to {is_admin}"}


@app.get("/api/admin/bots")
async def get_all_bots(current_user: User = Depends(get_current_user)):
    """Get all bots (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Refresh bot list to ensure we have up-to-date information
    await bot_manager.refresh_bot_list()
    
    # Get all bots from the database
    db_bots = list(bots_collection.find())
    
    # Convert MongoDB ObjectIDs to strings
    for bot in db_bots:
        bot["_id"] = str(bot["_id"])
    
    # Get real-time status for all bots
    for bot in db_bots:
        owner_id = bot["owner_id"]
        bot_name = bot["name"]
        
        user_bots = bot_manager.get_user_bots(owner_id)
        
        if bot_name in user_bots:
            bot["status"] = user_bots[bot_name]["status"]
            bot["container_id"] = user_bots[bot_name]["container_id"]
        else:
            bot["status"] = "stopped"
    
    return {"bots": db_bots}


@app.get("/api/admin/stats")
async def get_system_stats(current_user: User = Depends(get_current_user)):
    """Get system statistics (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Get Docker stats
    docker_client = bot_manager.container_manager.docker_client
    info = docker_client.info()
    
    containers = docker_client.containers.list()
    container_count = len(containers)
    running_count = sum(1 for c in containers if c.status == "running")
    
    # Get system stats
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    # Get user and bot counts
    user_count = users_collection.count_documents({})
    bot_count = bots_collection.count_documents({})
    
    return {
        "docker": {
            "version": info.get("ServerVersion", "Unknown"),
            "containers": container_count,
            "running_containers": running_count,
            "images": len(docker_client.images.list())
        },
        "system": {
            "os": info.get("OperatingSystem", "Unknown"),
            "architecture": info.get("Architecture", "Unknown"),
            "cpus": info.get("NCPU", "Unknown"),
            "cpu_usage": psutil.cpu_percent(),
            "memory": {
                "percent": memory.percent,
                "used_gb": memory.used // (1024**3),
                "total_gb": memory.total // (1024**3)
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": disk.used // (1024**3),
                "total_gb": disk.total // (1024**3)
            }
        },
        "app": {
            "user_count": user_count,
            "bot_count": bot_count,
            "data_directory": bot_manager.config["data_dir"]
        }
    }


# API documentation
@app.get("/api/docs", include_in_schema=False)
async def get_documentation(request: Request):
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="OpenShapes Manager API"
    )


@app.get("/api/openapi.json", include_in_schema=False)
async def get_openapi():
    return get_openapi(
        title="OpenShapes Manager API",
        version="1.0.0",
        description="API for managing OpenShapes bots",
        routes=app.routes,
    )


# Start the bot manager in a background thread
def start_bot_manager_thread():
    import threading
    
    def run_bot():
        try:
            logger.info("Starting OpenShapes Manager Discord bot...")
            import nest_asyncio
            nest_asyncio.apply()
            
            # Make sure the bot manager uses the correct token from environment variables
            discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")
            if not discord_bot_token:
                logger.error("DISCORD_BOT_TOKEN environment variable not set!")
                return
            
            bot_manager.run(discord_bot_token)
        except Exception as e:
            logger.error(f"Error running OpenShapes Manager bot: {e}")
    
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True  # This ensures the thread will exit when the main program exits
    bot_thread.start()
    logger.info("OpenShapes Manager Discord bot thread started")

# Main function
if __name__ == "__main__":
    import uvicorn
    
    # Start the Discord bot in the background
    start_bot_manager_thread()
    
    # Then start the FastAPI application
    uvicorn.run(app, host="127.0.0.1", port=8000)