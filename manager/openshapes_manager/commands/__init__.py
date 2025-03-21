from discord import app_commands

from .create_commands import setup_create_commands
from .manage_commands import setup_manage_commands
from .admin_commands import setup_admin_commands
from .tutorial_commands import setup_tutorial_commands

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
    setup_create_commands(bot, create_commands)
    setup_manage_commands(bot, manage_commands)
    setup_admin_commands(bot, admin_commands)
    setup_tutorial_commands(bot, tutorial_commands)
    
    return create_commands, manage_commands, admin_commands, tutorial_commands
