import re
import json
import os
import logging
from typing import Dict, Optional, List, Any, Protocol, Set
from enum import Enum, auto

logger = logging.getLogger("openshape")

class TextType(Enum):
    USER_INPUT = auto()
    AI_RESPONSE = auto()
    SLASH_COMMAND = auto()
    WORLD_INFO = auto()
    REASONING = auto()
    
    @classmethod
    def from_string(cls, text_type: str) -> 'TextType':
        mapping = {
            "user_input": cls.USER_INPUT,
            "ai_response": cls.AI_RESPONSE,
            "slash_command": cls.SLASH_COMMAND,
            "world_info": cls.WORLD_INFO,
            "reasoning": cls.REASONING
        }
        return mapping.get(text_type, cls.USER_INPUT)

class RegexExecutionError(Exception):
    def __init__(self, script_name: str, pattern: str, message: str):
        self.script_name = script_name
        self.pattern = pattern
        self.message = message
        super().__init__(f"Error in regex script '{script_name}' with pattern '{pattern}': {message}")

class TextProcessor(Protocol):
    def process(self, text: str) -> str:
        pass

class RegexScriptConfig:
    def __init__(
        self,
        name: str,
        find_pattern: str,
        replace_with: str,
        trim_out: str = "",
        disabled: bool = False
    ):
        self.name = name
        self.find_pattern = find_pattern
        self.replace_with = replace_with
        self.trim_out = trim_out
        self.disabled = disabled
        self.affected_text_types: Set[TextType] = {TextType.USER_INPUT, TextType.AI_RESPONSE}
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "find_pattern": self.find_pattern,
            "replace_with": self.replace_with,
            "trim_out": self.trim_out,
            "disabled": self.disabled,
            "affects_user_input": TextType.USER_INPUT in self.affected_text_types,
            "affects_ai_response": TextType.AI_RESPONSE in self.affected_text_types,
            "affects_slash_commands": TextType.SLASH_COMMAND in self.affected_text_types,
            "affects_world_info": TextType.WORLD_INFO in self.affected_text_types,
            "affects_reasoning": TextType.REASONING in self.affected_text_types
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegexScriptConfig':
        config = cls(
            data.get("name", "Unnamed Script"),
            data.get("find_pattern", ""),
            data.get("replace_with", ""),
            data.get("trim_out", ""),
            data.get("disabled", False)
        )
        
        affected_types = set()
        if data.get("affects_user_input", True):
            affected_types.add(TextType.USER_INPUT)
        if data.get("affects_ai_response", True):
            affected_types.add(TextType.AI_RESPONSE)
        if data.get("affects_slash_commands", False):
            affected_types.add(TextType.SLASH_COMMAND)
        if data.get("affects_world_info", False):
            affected_types.add(TextType.WORLD_INFO)
        if data.get("affects_reasoning", False):
            affected_types.add(TextType.REASONING)
            
        config.affected_text_types = affected_types
        return config

class RegexScript(TextProcessor):
    def __init__(self, config: RegexScriptConfig):
        self.config = config
        self._compiled_pattern: Optional[re.Pattern] = None
        self._compile_pattern()
        
    def _compile_pattern(self) -> None:
        try:
            if self.config.find_pattern:
                self._compiled_pattern = re.compile(self.config.find_pattern)
        except re.error as e:
            logger.error(f"Error compiling regex pattern '{self.config.find_pattern}': {e}")
            self._compiled_pattern = None
        
    def process(self, text: str) -> str:
        if self.config.disabled or not text or not self._compiled_pattern:
            return text
            
        try:
            result = self._compiled_pattern.sub(self.config.replace_with, text)
            
            if self.config.trim_out and self.config.trim_out in result:
                result = result.replace(self.config.trim_out, "")
                
            return result
        except Exception as e:
            logger.error(f"Error applying regex script {self.config.name}: {e}")
            raise RegexExecutionError(self.config.name, self.config.find_pattern, str(e))
            
    @property
    def name(self) -> str:
        return self.config.name
        
    @property
    def disabled(self) -> bool:
        return self.config.disabled
        
    @disabled.setter
    def disabled(self, value: bool) -> None:
        self.config.disabled = value
            
    def applies_to_text_type(self, text_type: TextType) -> bool:
        return text_type in self.config.affected_text_types
        
    def to_dict(self) -> Dict[str, Any]:
        return self.config.to_dict()
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegexScript':
        config = RegexScriptConfig.from_dict(data)
        return cls(config)

class MacroProcessor:
    @staticmethod
    def apply_macros(text: str, macros: Dict[str, str]) -> str:
        if not text or not macros:
            return text
            
        result = text
        for key, value in macros.items():
            result = result.replace(f"{{{key}}}", value)
            
        return result

class RegexScriptRegistry:
    def __init__(self, scripts_path: str):
        self.scripts_path = scripts_path
        self.scripts: List[RegexScript] = []
        
    def load_scripts(self) -> None:
        if not os.path.exists(self.scripts_path):
            self.scripts = []
            return
            
        try:
            with open(self.scripts_path, 'r', encoding='utf-8') as f:
                scripts_data = json.load(f)
                
            self.scripts = [RegexScript.from_dict(script_data) for script_data in scripts_data]
            logger.info(f"Loaded {len(self.scripts)} regex scripts")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing regex scripts JSON: {e}")
            self.scripts = []
        except Exception as e:
            logger.error(f"Error loading regex scripts: {e}")
            self.scripts = []
            
    def save_scripts(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.scripts_path), exist_ok=True)
            
            with open(self.scripts_path, 'w', encoding='utf-8') as f:
                scripts_data = [script.to_dict() for script in self.scripts]
                json.dump(scripts_data, f, indent=2)
                
            logger.info(f"Saved {len(self.scripts)} regex scripts")
        except Exception as e:
            logger.error(f"Error saving regex scripts: {e}")
            
    def add_script(self, name: str, find_pattern: str, replace_with: str) -> bool:
        if self.get_script(name) is not None:
            return False
            
        config = RegexScriptConfig(name, find_pattern, replace_with)
        script = RegexScript(config)
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
        
    def get_script(self, name: str, default_name: Optional[str] = None) -> Optional[RegexScript]:
        name_lower = name.lower()
        
        for script in self.scripts:
            if script.name.lower() == name_lower:
                return script
                
        if default_name and name_lower == default_name.lower():
            config = RegexScriptConfig(default_name, "", "")
            return RegexScript(config)
            
        return None

class RegexManager:
    def __init__(self, bot: Any):
        self.bot = bot
        self.scripts_path = os.path.join(bot.data_dir, "regex_scripts.json")
        self.registry = RegexScriptRegistry(self.scripts_path)
        self.registry.load_scripts()
        
    @property
    def scripts(self) -> List[RegexScript]:
        return self.registry.scripts
        
    def load_scripts(self) -> None:
        self.registry.load_scripts()
        
    def save_scripts(self) -> None:
        self.registry.save_scripts()
        
    def add_script(self, name: str, find_pattern: str, replace_with: str) -> bool:
        return self.registry.add_script(name, find_pattern, replace_with)
        
    def remove_script(self, name: str) -> bool:
        return self.registry.remove_script(name)
        
    def get_script(self, name: str, default_name: Optional[str] = None) -> Optional[RegexScript]:
        return self.registry.get_script(name, default_name)
        
    def process_text(self, text: str, text_type_str: str, macros: Optional[Dict[str, str]] = None) -> str:
        if not text:
            return text
            
        text_type = TextType.from_string(text_type_str)

        if macros:
            text = MacroProcessor.apply_macros(text, macros)

        for script in self.scripts:
            if script.disabled:
                continue
                
            if script.applies_to_text_type(text_type):
                try:
                    text = script.process(text)
                except RegexExecutionError as e:
                    logger.warning(str(e))
                
        return text
