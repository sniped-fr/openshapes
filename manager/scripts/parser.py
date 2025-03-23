import json
import datetime
import os
import uuid
from typing import Dict, List, Optional, Any

class FileHandler:
    @staticmethod
    def load_json(file_path: str) -> dict:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @staticmethod
    def save_json(data: Any, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def ensure_directory(directory_path: str) -> None:
        os.makedirs(directory_path, exist_ok=True)

class CharacterConfigBuilder:
    def __init__(self, shapes_data: Dict[str, Any]):
        self.shapes_data = shapes_data
        self.discord_bot_token = "NOT_PROVIDED"
        self.owner_id = self._extractbot_owner_id()
        self.character_name = shapes_data.get("name", "Unknown")
        
    def _extractbot_owner_id(self) -> Optional[int]:
        if "app_info" in self.shapes_data and "full_data" in self.shapes_data["app_info"]:
            app_data = self.shapes_data["app_info"]["full_data"]
            if "owner" in app_data and "id" in app_data["owner"]:
                return int(app_data["owner"]["id"])
        return None

    def build_system_prompt(self) -> str:
        system_prompt = f"You are {self.character_name}. "
        
        personality_history = self.shapes_data.get("personality_history", "")
        if personality_history:
            system_prompt += f"{personality_history} "
        
        personality_traits = self.shapes_data.get("personality_traits", "")
        if personality_traits:
            system_prompt += f"You are {personality_traits}. "
        
        personality_tone = self.shapes_data.get("personality_tone", "")
        if personality_tone:
            system_prompt += f"Your tone is {personality_tone}. "
            
        return system_prompt.strip()
    
    def build_character_description(self) -> str:
        character_description = f"{self.character_name} "
        
        personality_physical_traits = self.shapes_data.get("personality_physical_traits", None)
        if personality_physical_traits:
            character_description += f"has {personality_physical_traits}. "
        
        if (
            "shape_settings" in self.shapes_data
            and "appearance" in self.shapes_data["shape_settings"]
        ):
            character_description += self.shapes_data["shape_settings"]["appearance"]
            
        return character_description.strip()
    
    def build_character_scenario(self) -> str:
        personality_conversational_goals = self.shapes_data.get("personality_conversational_goals", "")
        if personality_conversational_goals:
            return personality_conversational_goals.replace("{user}", "[user]")
        return ""
    
    def create_config(self) -> Dict[str, Any]:
        system_prompt = self.build_system_prompt()
        character_description = self.build_character_description()
        character_scenario = self.build_character_scenario()
        
        return {
            "bot_token": self.discord_bot_token,
            "owner_id": self.owner_id,
            "character_name": self.character_name,
            "allowed_guilds": [],
            "command_prefix": "!",
            "system_prompt": system_prompt,
            "character_backstory": self.shapes_data.get("user_prompt", "").strip(),
            "character_description": character_description,
            "personality_catchphrases": self.shapes_data.get("personality_catchphrases", None) or "",
            "personality_age": self.shapes_data.get("personality_age", "Unknown age"),
            "personality_likes": self.shapes_data.get("personality_likes", ""),
            "personality_dislikes": self.shapes_data.get("personality_dislikes", ""),
            "personality_goals": self.shapes_data.get("personality_goals", None) or "",
            "personality_traits": self.shapes_data.get("personality_traits", ""),
            "personality_physical_traits": self.shapes_data.get("personality_physical_traits", None) or "",
            "personality_tone": self.shapes_data.get("personality_tone", ""),
            "personality_history": self.shapes_data.get("personality_history", ""),
            "personality_conversational_goals": self.shapes_data.get(
                "personality_conversational_goals", ""
            ).replace("{user}", "[user]"),
            "personality_conversational_examples": self.shapes_data.get(
                "personality_conversational_examples", ""
            ).replace("{user}", "[user]"),
            "character_scenario": character_scenario,
            "free_will": self.shapes_data.get("free_will", False),
            "free_will_instruction": self.shapes_data.get("free_will_instruction", "") or "",
            "jailbreak": self.shapes_data.get("jailbreak", "") or "",
            "add_character_name": False,
            "reply_to_name": True,
            "always_reply_mentions": True,
            "use_tts": True,
            "data_dir": "character_data",
            "api_settings": {
                "base_url": "https://api.zukijourney.com/v1",
                "api_key": "zu-myballs",
                "chat_model": "llama-3.1-8b-instruct",
                "tts_model": "speechify",
                "tts_voice": "mrbeast",
            },
            "activated_channels": [],
            "blacklisted_users": [],
            "blacklisted_roles": [],
            "conversation_timeout": 30,
        }

class MemoryEntry:
    def __init__(self, key: str, detail: str, source: str, timestamp: str):
        self.key = key
        self.detail = detail
        self.source = source
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "detail": self.detail,
            "source": self.source,
            "timestamp": self.timestamp
        }

class MemoryManager:
    def __init__(self, shapes_data: Dict[str, Any], brain_data: List[Dict[str, Any]]):
        self.shapes_data = shapes_data
        self.brain_data = brain_data
        self.character_name = shapes_data.get("name", "Unknown")
        self.current_time = datetime.datetime.now().isoformat()
        self.memory_entries: Dict[str, MemoryEntry] = {}
        
    def create_base_entries(self) -> None:
        self.add_entry(
            f"{self.character_name}'s Identity",
            f"{self.character_name} is a character with a unique personality",
            "Character Configuration"
        )
        
        if personality_traits := self.shapes_data.get("personality_traits"):
            self.add_entry(
                f"{self.character_name}'s Traits",
                personality_traits,
                "Character Configuration"
            )
        
        if personality_history := self.shapes_data.get("personality_history"):
            self.add_entry(
                f"{self.character_name}'s Background",
                personality_history,
                "Character Configuration"
            )
    
    def add_entry(self, key: str, detail: str, source: str) -> None:
        self.memory_entries[key] = MemoryEntry(key, detail, source, self.current_time)
    
    def add_brain_entries(self) -> None:
        for entry in self.brain_data:
            self._process_brain_entry(entry)
    
    def _process_brain_entry(self, entry: Dict[str, Any]) -> None:
        story_type = entry["story_type"]
        content = entry["content"]
        
        if story_type == "general" and content != "Insert general knowledge here":
            self._add_random_key_entry(f"General Knowledge {self._generate_uuid()}", content, "Brain Data")
        
        elif story_type == "personal" and content != 'Insert "personal" custom added sorting option for knowledge here':
            self._add_random_key_entry(f"Personal Detail {self._generate_uuid()}", content, "Personal Knowledge")
        
        elif story_type == "relationships" and content != "Insert relationship here":
            self._add_random_key_entry(f"Relationship {self._generate_uuid()}", content, "Relationship Data")
        
        elif story_type == "commands" and content != "Insert command here ":
            self._add_random_key_entry(f"Command Knowledge {self._generate_uuid()}", content, "Command Data")
    
    def _generate_uuid(self) -> str:
        return str(uuid.uuid4())[:8]
    
    def _add_random_key_entry(self, key_prefix: str, detail: str, source: str) -> None:
        self.add_entry(key_prefix, detail, source)
    
    def to_dict(self) -> Dict[str, Dict[str, str]]:
        return {k: v.to_dict() for k, v in self.memory_entries.items()}

class LoreBookEntry:
    def __init__(self, title: str, content: str):
        self.title = title
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {self.title: self.content}

class LoreBookManager:
    def __init__(self, brain_data: List[Dict[str, Any]]):
        self.brain_data = brain_data
        self.entries: List[LoreBookEntry] = []
    
    def process_entries(self) -> None:
        for entry in self.brain_data:
            self._process_brain_entry(entry)
    
    def _process_brain_entry(self, entry: Dict[str, Any]) -> None:
        story_type = entry["story_type"]
        content = entry["content"]
        
        if (story_type == "general" and content != "Insert general knowledge here") or (
            story_type == "personal" and content != 'Insert "personal" custom added sorting option for knowledge here'
        ):
            title = self._create_title(content)
            self.entries.append(LoreBookEntry(title, content))
    
    def _create_title(self, content: str) -> str:
        words = content.split()
        if len(words) > 5:
            return " ".join(words[:5]) + "..."
        return content
    
    def to_list(self) -> List[Dict[str, str]]:
        return [entry.to_dict() for entry in self.entries]

class ShapesParser:
    def __init__(self, shapes_json_path: str, brain_json_path: Optional[str] = None):
        self.file_handler = FileHandler()
        self.shapes_json_path = shapes_json_path
        self.brain_json_path = brain_json_path
        self.shapes_data = {}
        self.brain_data = []
        self.parsed_data: Dict[str, Any] = {}
    
    def load_data(self) -> None:
        self.shapes_data = self.file_handler.load_json(self.shapes_json_path)
        
        if self.brain_json_path and os.path.exists(self.brain_json_path):
            self.brain_data = self.file_handler.load_json(self.brain_json_path)
    
    def parse(self) -> Dict[str, Any]:
        self.load_data()
        
        config_builder = CharacterConfigBuilder(self.shapes_data)
        character_config = config_builder.create_config()
        
        memory_manager = MemoryManager(self.shapes_data, self.brain_data)
        memory_manager.create_base_entries()
        memory_manager.add_brain_entries()
        memory_data = memory_manager.to_dict()
        
        lorebook_manager = LoreBookManager(self.brain_data)
        lorebook_manager.process_entries()
        lorebook_data = lorebook_manager.to_list()
        
        self.parsed_data = {
            "character_config": character_config,
            "memory": memory_data,
            "lorebook": lorebook_data,
        }
        
        return self.parsed_data
    
    def save_parsed_data(self, output_dir: str = ".") -> None:
        if not self.parsed_data:
            raise ValueError("No parsed data available. Call parse() first.")
        
        self.file_handler.ensure_directory(output_dir)
        self.file_handler.ensure_directory(os.path.join(output_dir, "character_data"))
        
        self.file_handler.save_json(
            self.parsed_data["character_config"],
            os.path.join(output_dir, "character_config.json")
        )
        
        self.file_handler.save_json(
            self.parsed_data["memory"],
            os.path.join(output_dir, "character_data", "memory.json")
        )
        
        self.file_handler.save_json(
            self.parsed_data["lorebook"],
            os.path.join(output_dir, "character_data", "lorebook.json")
        )
        
        print(f"Files saved to {output_dir}")

class ParserApplication:
    def __init__(self):
        self.shapes_json_path = "./config.json"
        self.brain_json_path = "./brain.json" if os.path.exists("./brain.json") else None
        self.output_dir = "."
    
    def run(self) -> None:
        try:
            self._log_startup_info()
            parser = ShapesParser(self.shapes_json_path, self.brain_json_path)
            parser.parse()
            parser.save_parsed_data(self.output_dir)
            print("Conversion completed successfully!")
            
        except FileNotFoundError as e:
            print(f"Error: File not found - {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON format - {e}")
            raise
        except Exception as e:
            print(f"Error: {e}")
            raise
    
    def _log_startup_info(self) -> None:
        print(f"Parsing shapes data from {self.shapes_json_path}")
        if self.brain_json_path:
            print(f"Using brain data from {self.brain_json_path}")
        else:
            print("No brain data file found, proceeding without brain data")

if __name__ == "__main__":
    app = ParserApplication()
    app.run()