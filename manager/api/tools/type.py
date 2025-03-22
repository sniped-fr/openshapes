
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

# Pydantic models
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserBase(BaseModel):
    username: str
    discriminator: Optional[str] = None
    avatar: Optional[str] = None


class User(UserBase):
    id: str
    bot_credits: int = 3
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime = Field(default_factory=datetime.utcnow)


class UserOut(UserBase):
    id: str
    bot_credits: int
    is_admin: bool


class BotBase(BaseModel):
    name: str
    description: Optional[str] = None


class BotCreate(BotBase):
    bot_token: str
    config: Dict[str, Any]
    brain_data: Optional[Dict[str, Any]] = None


class BotUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class BotOut(BotBase):
    id: str
    owner_id: str
    status: str
    container_id: Optional[str] = None
    created_at: datetime


class APISettingsUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    chat_model: Optional[str] = None
    tts_model: Optional[str] = None
    tts_voice: Optional[str] = None

class DirectBotCreate(BaseModel):
    bot_token: str
    character_name: str
    character_backstory: str
    system_prompt: Optional[str] = ""
    character_description: Optional[str] = ""
    personality_catchphrases: Optional[str] = ""
    personality_age: Optional[str] = "Unknown age"
    personality_likes: Optional[str] = ""
    personality_dislikes: Optional[str] = ""
    personality_goals: Optional[str] = ""
    personality_traits: Optional[str] = ""
    personality_physical_traits: Optional[str] = ""
    personality_tone: Optional[str] = ""
    personality_history: Optional[str] = ""
    personality_conversational_goals: Optional[str] = ""
    personality_conversational_examples: Optional[str] = ""
    character_scenario: Optional[str] = ""
    free_will: bool = False
    free_will_instruction: Optional[str] = ""
    jailbreak: Optional[str] = ""
    add_character_name: bool = False
    reply_to_name: bool = True
    always_reply_mentions: bool = True
    use_tts: bool = True
    api_base_url: Optional[str] = "https://api.zukijourney.com/v1"
    api_key: Optional[str] = "zu-myballs"
    chat_model: Optional[str] = "llama-3.1-8b-instruct"
    tts_model: Optional[str] = "speechify"
    tts_voice: Optional[str] = "mrbeast"

