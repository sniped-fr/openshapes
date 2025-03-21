import re
import json
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger("openshape")

class RegexScript:
    def __init__(self, name: str, find_pattern: str, replace_with: str):
        self.name = name
        self.find_pattern = find_pattern
        self.replace_with = replace_with
        self.trim_out = ""
        self.disabled = False
        self.affects_user_input = True
        self.affects_ai_response = True
        self.affects_slash_commands = False
        self.affects_world_info = False
        self.affects_reasoning = False
        
    def apply(self, text: str) -> str:
        if self.disabled:
            return text
            
        try:
            result = re.sub(self.find_pattern, self.replace_with, text)
            
            if self.trim_out and self.trim_out in result:
                result = result.replace(self.trim_out, "")
                
            return result
        except Exception as e:
            logger.error(f"Error applying regex script {self.name}: {e}")
            return text
            
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "find_pattern": self.find_pattern,
            "replace_with": self.replace_with,
            "trim_out": self.trim_out,
            "disabled": self.disabled,
            "affects_user_input": self.affects_user_input,
            "affects_ai_response": self.affects_ai_response,
            "affects_slash_commands": self.affects_slash_commands,
            "affects_world_info": self.affects_world_info,
            "affects_reasoning": self.affects_reasoning
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'RegexScript':
        script = cls(
            data.get("name", "Unnamed Script"),
            data.get("find_pattern", ""),
            data.get("replace_with", "")
        )
        script.trim_out = data.get("trim_out", "")
        script.disabled = data.get("disabled", False)
        script.affects_user_input = data.get("affects_user_input", True)
        script.affects_ai_response = data.get("affects_ai_response", True)
        script.affects_slash_commands = data.get("affects_slash_commands", False)
        script.affects_world_info = data.get("affects_world_info", False)
        script.affects_reasoning = data.get("affects_reasoning", False)
        return script

class RegexManager:
    def __init__(self, bot):
        self.bot = bot
        self.scripts_path = os.path.join(bot.data_dir, "regex_scripts.json")
        self.scripts = []
        self.load_scripts()
        
    def load_scripts(self):
        if os.path.exists(self.scripts_path):
            try:
                with open(self.scripts_path, 'r', encoding='utf-8') as f:
                    scripts_data = json.load(f)
                    
                self.scripts = [RegexScript.from_dict(script_data) for script_data in scripts_data]
                logger.info(f"Loaded {len(self.scripts)} regex scripts")
            except Exception as e:
                logger.error(f"Error loading regex scripts: {e}")
                self.scripts = []
        else:
            self.scripts = []
            
    def save_scripts(self):
        try:
            with open(self.scripts_path, 'w', encoding='utf-8') as f:
                scripts_data = [script.to_dict() for script in self.scripts]
                json.dump(scripts_data, f, indent=2)
            logger.info(f"Saved {len(self.scripts)} regex scripts")
        except Exception as e:
            logger.error(f"Error saving regex scripts: {e}")
            
    def add_script(self, name: str, find_pattern: str, replace_with: str) -> bool:
        if self.get_script(name) is not None:
            return False
            
        script = RegexScript(name, find_pattern, replace_with)
        self.scripts.append(script)
        self.save_scripts()
        return True
        
    def remove_script(self, name: str) -> bool:
        script = self.get_script(name)
        if script is None:
            return False
            
        self.scripts.remove(script)
        self.save_scripts()
        return True
        
    def get_script(self, name: str, default_name: str = None) -> Optional[RegexScript]:
        for script in self.scripts:
            if script.name.lower() == name.lower():
                return script
                
        if default_name and name.lower() == default_name.lower():
            return RegexScript(default_name, "", "")
            
        return None
        
    def process_text(self, text: str, text_type: str, macros: Dict[str, str] = None) -> str:
        if not text:
            return text
            
        if macros:
            for key, value in macros.items():
                text = text.replace(f"{{{key}}}", value)
                
        for script in self.scripts:
            if script.disabled:
                continue
                
            if text_type == "user_input" and script.affects_user_input:
                text = script.apply(text)
            elif text_type == "ai_response" and script.affects_ai_response:
                text = script.apply(text)
            elif text_type == "slash_command" and script.affects_slash_commands:
                text = script.apply(text)
            elif text_type == "world_info" and script.affects_world_info:
                text = script.apply(text)
            elif text_type == "reasoning" and script.affects_reasoning:
                text = script.apply(text)
                
        return text
