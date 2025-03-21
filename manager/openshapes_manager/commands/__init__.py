from typing import Dict, Tuple
from discord import app_commands
from openshapes_manager.commands.create_commands import setup_create_commands
from openshapes_manager.commands.manage_commands import setup_manage_commands 
from openshapes_manager.commands.admin_commands import setup_admin_commands
from openshapes_manager.commands.tutorial_commands import setup_tutorial_commands

class CommandRegistry:
    def __init__(self):
        self.command_groups: Dict[str, app_commands.Group] = {}
        self._initialize_command_groups()
    
    def _initialize_command_groups(self) -> None:
        self.command_groups["create"] = app_commands.Group(
            name="create", description="Create a new OpenShapes bot"
        )
        
        self.command_groups["manage"] = app_commands.Group(
            name="manage", description="Manage your OpenShapes bots"
        )
        
        self.command_groups["admin"] = app_commands.Group(
            name="admin", description="Admin commands for bot management"
        )
        
        self.command_groups["tutorial"] = app_commands.Group(
            name="tutorial", description="Get help with OpenShapes setup"
        )
    
    def get_group(self, name: str) -> app_commands.Group:
        return self.command_groups.get(name)
    
    def get_all_groups(self) -> Tuple[app_commands.Group, ...]:
        return (
            self.command_groups["create"],
            self.command_groups["manage"],
            self.command_groups["admin"],
            self.command_groups["tutorial"]
        )


class CommandManager:
    def __init__(self, bot):
        self.bot = bot
        self.registry = CommandRegistry()
    
    def setup_commands(self) -> Tuple[app_commands.Group, ...]:
        create_commands = self.registry.get_group("create")
        manage_commands = self.registry.get_group("manage")
        admin_commands = self.registry.get_group("admin")
        tutorial_commands = self.registry.get_group("tutorial")
        
        setup_create_commands(self.bot, create_commands)
        setup_manage_commands(self.bot, manage_commands)
        setup_admin_commands(self.bot, admin_commands)
        setup_tutorial_commands(self.bot, tutorial_commands)
        
        return self.registry.get_all_groups()


# Maintain backwards compatibility with existing code
create_commands = app_commands.Group(
    name="create", description="Create a new OpenShapes bot"
)

manage_commands = app_commands.Group(
    name="manage", description="Manage your OpenShapes bots"
)

admin_commands = app_commands.Group(
    name="admin", description="Admin commands for bot management"
)

tutorial_commands = app_commands.Group(
    name="tutorial", description="Get help with OpenShapes setup"
)


def setup_commands(bot):
    command_manager = CommandManager(bot)
    return command_manager.setup_commands()
