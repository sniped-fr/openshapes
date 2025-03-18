from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import json
import os
import httpx
import logging
import pymongo
from bson.objectid import ObjectId
import asyncio
from bot_manager import BotManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("character_api")

# Initialize FastAPI app
app = FastAPI(title="Character Bots API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Discord OAuth2 setup
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://discord.com/api/oauth2/authorize",
    tokenUrl="https://discord.com/api/oauth2/token",
    scopes={"identify", "guilds"}
)

# Configuration
with open("config.json", "r") as f:
    config = json.load(f)

# MongoDB connection
client = pymongo.MongoClient(config["mongodb_uri"])
db = client[config["database_name"]]
users_collection = db["users"]
bots_collection = db["bots"]

# Bot manager instance
bot_manager = None


# Pydantic models
class User(BaseModel):
    id: str
    username: str
    discriminator: str
    avatar: Optional[str] = None
    bot_credits: int = 0


class CharacterConfig(BaseModel):
    character_name: str
    ai_provider: str
    ai_api_key: str
    system_prompt: str
    character_description: str
    character_personality: str
    character_scenario: str
    add_character_name: bool = True
    reply_to_name: bool = True
    always_reply_mentions: bool = True
    max_history_length: int = 10
    allowed_guilds: List[int] = []


class BotUpdateRequest(BaseModel):
    updates: Dict[str, Any]


class BotCreationResponse(BaseModel):
    bot_id: str
    message: str


# Authentication dependency
async def get_current_user(token: str = Depends(oauth2_scheme)):
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("https://discord.com/api/users/@me", headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_data = response.json()
        
        # Check if user exists in database, create if not
        user = users_collection.find_one({"id": user_data["id"]})
        if not user:
            new_user = {
                "id": user_data["id"],
                "username": user_data["username"],
                "discriminator": user_data["discriminator"],
                "avatar": user_data.get("avatar"),
                "bot_credits": config["default_bot_credits"]
            }
            users_collection.insert_one(new_user)
            user = new_user
        
        return User(**user)


# Startup event
@app.on_event("startup")
async def startup_event():
    global bot_manager
    bot_manager = BotManager(config["bot_manager_config"])
    await bot_manager.start()


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    if bot_manager:
        await bot_manager.stop()


# Routes
@app.get("/api/user", response_model=User)
async def get_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/api/user/bots")
async def get_user_bots(current_user: User = Depends(get_current_user)):
    bots = await bot_manager.get_user_bots(current_user.id)
    return {"bots": bots}


@app.post("/api/bots", response_model=BotCreationResponse)
async def create_bot(
    character_config: CharacterConfig,
    current_user: User = Depends(get_current_user)
):
    # Check if user has bot credits
    user = users_collection.find_one({"id": current_user.id})
    if user["bot_credits"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Not enough bot credits"
        )
    
    # Create the bot
    bot_id = await bot_manager.create_bot(current_user.id, character_config.dict())
    if not bot_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bot"
        )
    
    return {"bot_id": bot_id, "message": "Bot created successfully"}


@app.get("/api/bots/{bot_id}")
async def get_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    bot = bots_collection.find_one({"_id": bot_id})
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this bot"
        )
    
    # Get bot status
    status = await bot_manager.get_bot_status(bot_id)
    bot["status"] = status
    
    return bot


@app.put("/api/bots/{bot_id}")
async def update_bot(
    bot_id: str,
    request: BotUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    bot = bots_collection.find_one({"_id": bot_id})
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this bot"
        )
    
    # Update the bot
    success = await bot_manager.update_bot(bot_id, request.updates)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bot"
        )
    
    return {"message": "Bot updated successfully"}


@app.delete("/api/bots/{bot_id}")
async def delete_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    bot = bots_collection.find_one({"_id": bot_id})
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this bot"
        )
    
    # Delete the bot
    success = await bot_manager.delete_bot(bot_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete bot"
        )
    
    # Refund a bot credit
    users_collection.update_one(
        {"id": current_user.id},
        {"$inc": {"bot_credits": 1}}
    )
    
    return {"message": "Bot deleted successfully and credit refunded"}


@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    bot = bots_collection.find_one({"_id": bot_id})
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control this bot"
        )
    
    # Start the bot
    success = await bot_manager.start_bot(bot_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start bot"
        )
    
    return {"message": "Bot started successfully"}


@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    bot = bots_collection.find_one({"_id": bot_id})
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control this bot"
        )
    
    # Stop the bot
    success = await bot_manager.stop_bot(bot_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop bot"
        )
    
    return {"message": "Bot stopped successfully"}


@app.post("/api/bots/{bot_id}/restart")
async def restart_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    bot = bots_collection.find_one({"_id": bot_id})
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    if bot["owner_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to control this bot"
        )
    
    # Restart the bot
    success = await bot_manager.restart_bot(bot_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restart bot"
        )
    
    return {"message": "Bot restarted successfully"}


# API routes for admin functions
@app.post("/api/admin/add_credits/{user_id}")
async def add_credits(
    user_id: str, 
    credits: int = 1,
    current_user: User = Depends(get_current_user)
):
    # Check if current user is admin
    if current_user.id not in config["admin_users"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can add credits"
        )
    
    # Add credits to user
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


# Run with: uvicorn api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)