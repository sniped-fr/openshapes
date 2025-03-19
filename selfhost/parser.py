import json
import datetime
import os
import uuid

def parse_shapes_data(shapes_json_path, brain_json_path=None):
    """
    Parse shapes.json and brain.json into character_config.json, memory.json, and lorebook.json
    
    Args:
        shapes_json_path: Path to shapes.json
        brain_json_path: Path to brain.json (optional)
    
    Returns:
        Dictionary containing the parsed data structures
    """
    # Load shapes data
    with open(shapes_json_path, 'r', encoding='utf-8') as f:
        shapes_data = json.load(f)
    
    # Load brain data if provided
    brain_data = []
    if brain_json_path and os.path.exists(brain_json_path):
        with open(brain_json_path, 'r', encoding='utf-8') as f:
            brain_data = json.load(f)
    
    # Parse character_config.json
    character_config = create_character_config(shapes_data)
    
    # Parse memory.json from brain data
    memory_data = create_memory_json(brain_data, shapes_data)
    
    # Parse lorebook.json from brain data
    lorebook_data = create_lorebook_json(brain_data)
    
    return {
        "character_config": character_config,
        "memory": memory_data,
        "lorebook": lorebook_data
    }

def create_character_config(shapes_data):
    """Create character_config.json from shapes_data"""
    # Extract discord bot information
    discord_bot_id = None
    discord_bot_token = "NOT_PROVIDED"  # Default placeholder
    
    if "app_info" in shapes_data and "full_data" in shapes_data["app_info"]:
        app_data = shapes_data["app_info"]["full_data"]
        if "bot" in app_data and "id" in app_data["bot"]:
            discord_bot_id = app_data["bot"]["id"]
        
        # Get owner info
        owner_id = None
        if "owner" in app_data and "id" in app_data["owner"]:
            owner_id = int(app_data["owner"]["id"])
    
    # Get character information
    character_name = shapes_data.get("name", "Unknown")
    
    # Extract personality traits
    personality_catchphrases = shapes_data.get("personality_catchphrases", None)
    personality_age = shapes_data.get("personality_age", "Unknown age")
    personality_likes = shapes_data.get("personality_likes", "")
    personality_dislikes = shapes_data.get("personality_dislikes", "")
    personality_goals = shapes_data.get("personality_goals", None)
    personality_traits = shapes_data.get("personality_traits", "")
    personality_physical_traits = shapes_data.get("personality_physical_traits", None)
    personality_tone = shapes_data.get("personality_tone", "")
    personality_history = shapes_data.get("personality_history", "")
    personality_conversational_goals = shapes_data.get("personality_conversational_goals", "")
    personality_conversational_examples = shapes_data.get("personality_conversational_examples", "")
    
    # Construct initial message
    initial_message = ""
    if "shape_settings" in shapes_data and "shape_initial_message" in shapes_data["shape_settings"]:
        initial_message = shapes_data["shape_settings"]["shape_initial_message"]
    
    # Construct system prompt
    system_prompt = f"You are {character_name}. "
    
    if personality_history:
        system_prompt += f"{personality_history} "
    
    if personality_traits:
        system_prompt += f"You are {personality_traits}. "
    
    if personality_tone:
        system_prompt += f"Your tone is {personality_tone}. "
    
    # Create character description
    character_description = f"{character_name} "
    if personality_physical_traits:
        character_description += f"has {personality_physical_traits}. "
    
    if "shape_settings" in shapes_data and "appearance" in shapes_data["shape_settings"]:
        character_description += shapes_data["shape_settings"]["appearance"]
    
    # Character scenario
    character_scenario = ""
    if personality_conversational_goals:
        character_scenario = personality_conversational_goals.replace("{user}", "[user]")
    
    # Create the character config object
    config = {
        "bot_token": discord_bot_token,
        "owner_id": owner_id,
        "character_name": character_name,
        "allowed_guilds": [],
        "command_prefix": "!",
        "system_prompt": system_prompt.strip(),
        "character_description": character_description.strip(),
        "personality_catchphrases": personality_catchphrases or "",
        "personality_age": personality_age,
        "personality_likes": personality_likes,
        "personality_dislikes": personality_dislikes,
        "personality_goals": personality_goals or "",
        "personality_traits": personality_traits,
        "personality_physical_traits": personality_physical_traits or "",
        "personality_tone": personality_tone,
        "personality_history": personality_history,
        "personality_conversational_goals": personality_conversational_goals.replace("{user}", "[user]"),
        "personality_conversational_examples": personality_conversational_examples.replace("{user}", "[user]"),
        "character_scenario": character_scenario,
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
            "tts_voice": "mrbeast"
        },
        "activated_channels": [],
        "blacklisted_users": [],
        "blacklisted_roles": [],
        "conversation_timeout": 30
    }
    
    return config

def create_memory_json(brain_data, shapes_data):
    """Create memory.json from brain_data"""
    memory = {}
    current_time = datetime.datetime.now().isoformat()
    character_name = shapes_data.get("name", "Unknown")
    
    # Add basic character information to memory
    memory[f"{character_name}'s Identity"] = {
        "detail": f"{character_name} is a character with a unique personality",
        "source": "Character Configuration",
        "timestamp": current_time
    }
    
    # Extract personality details for memory
    if shapes_data.get("personality_traits"):
        memory[f"{character_name}'s Traits"] = {
            "detail": shapes_data.get("personality_traits"),
            "source": "Character Configuration",
            "timestamp": current_time
        }
    
    if shapes_data.get("personality_history"):
        memory[f"{character_name}'s Background"] = {
            "detail": shapes_data.get("personality_history"),
            "source": "Character Configuration",
            "timestamp": current_time
        }
    
    # Process brain data
    for entry in brain_data:
        if entry["story_type"] == "general" and entry["content"] != "Insert general knowledge here":
            memory_key = f"General Knowledge {str(uuid.uuid4())[:8]}"
            memory[memory_key] = {
                "detail": entry["content"],
                "source": "Brain Data",
                "timestamp": current_time
            }
        
        elif entry["story_type"] == "personal" and entry["content"] != "Insert \"personal\" custom added sorting option for knowledge here":
            memory_key = f"Personal Detail {str(uuid.uuid4())[:8]}"
            memory[memory_key] = {
                "detail": entry["content"],
                "source": "Personal Knowledge",
                "timestamp": current_time
            }
        
        elif entry["story_type"] == "relationships" and entry["content"] != "Insert relationship here":
            memory_key = f"Relationship {str(uuid.uuid4())[:8]}"
            memory[memory_key] = {
                "detail": entry["content"],
                "source": "Relationship Data",
                "timestamp": current_time
            }
        
        elif entry["story_type"] == "commands" and entry["content"] != "Insert command here ":
            memory_key = f"Command Knowledge {str(uuid.uuid4())[:8]}"
            memory[memory_key] = {
                "detail": entry["content"],
                "source": "Command Data",
                "timestamp": current_time
            }
    
    return memory

def create_lorebook_json(brain_data):
    """Create lorebook.json from brain_data"""
    lorebook = []
    
    # Extract lore entries from brain data
    for entry in brain_data:
        # Skip default/template entries
        if (entry["story_type"] == "general" and entry["content"] != "Insert general knowledge here") or \
           (entry["story_type"] == "personal" and entry["content"] != "Insert \"personal\" custom added sorting option for knowledge here"):
            
            # Create a meaningful title based on the first few words of content
            content = entry["content"]
            title = " ".join(content.split()[:5]) + "..." if len(content.split()) > 5 else content
            
            # Add to lorebook with the title as key and value
            lorebook.append({title: content})
    
    return lorebook

def save_json_files(parsed_data, output_dir="."):
    """Save the parsed data to JSON files"""
    # Create the output directory and the character_data subdirectory
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "character_data"), exist_ok=True)
    
    # Save character_config.json
    with open(os.path.join(output_dir, "character_config.json"), 'w', encoding='utf-8') as f:
        json.dump(parsed_data["character_config"], f, indent=2)
    
    # Save memory.json
    with open(os.path.join(output_dir, "character_data", "memory.json"), 'w', encoding='utf-8') as f:
        json.dump(parsed_data["memory"], f, indent=2)
    
    # Save lorebook.json
    with open(os.path.join(output_dir, "character_data", "lorebook.json"), 'w', encoding='utf-8') as f:
        json.dump(parsed_data["lorebook"], f, indent=2)
    
    print(f"Files saved to {output_dir}")

def main():
    # Get file paths from user with defaults to current directory
    shapes_json_path = input("Enter the path to shapes.json (or press Enter for './shapes.json'): ") or "./shapes.json"
    brain_json_path = input("Enter the path to brain.json (or press Enter for './brain.json'): ") or "./brain.json"
    output_dir = input("Enter the output directory (or press Enter for current directory): ") or "."
    
    # Check if brain.json exists, set to None if it doesn't
    if not os.path.exists(brain_json_path):
        print(f"Note: {brain_json_path} not found. Proceeding without brain data.")
        brain_json_path = None
    
    try:
        # Parse data
        parsed_data = parse_shapes_data(shapes_json_path, brain_json_path)
        
        # Save to files
        save_json_files(parsed_data, output_dir)
        
        print("Conversion completed successfully!")
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()