import httpx

async def check_bot_token_intents(bot_token: str) -> tuple[bool, str]:
    """
    Check if a Discord bot token has the required privileged intents enabled.
    Returns (success, message) tuple.
    """
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # First, verify the token is valid by making a simple API call
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://discord.com/api/v10/users/@me", 
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code != 200:
                return False, f"Invalid bot token. Status code: {response.status_code}"
                
            # Get the application info to check privileged intents
            app_response = await client.get(
                "https://discord.com/api/v10/applications/@me", 
                headers=headers,
                timeout=10.0
            )

            if app_response.status_code != 200:
                return False, f"Failed to get application info. Status code: {app_response.status_code}"
                
            app_data = app_response.json()
            
            # Check flags for intents
            flags = app_data.get("flags", 0)
        
            if flags != 8953856:
                return False, f"Missing required privileged intents: Message Content Intent, Server Members Intent, Presence Intent. Please enable them in the Discord Developer Portal."
         
            return True, "All required intents are enabled"
            
    except Exception as e:
        return False, f"Error checking bot token: {str(e)}"