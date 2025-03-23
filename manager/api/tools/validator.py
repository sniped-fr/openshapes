import discord
import asyncio
from contextlib import AsyncExitStack

async def check_bot_token_intents(token):
    """Async function to check if a bot token has the required intents."""
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"✅ Successfully connected as {client.user}")
        print(f"✅ The following intents are enabled:")
        
        # List enabled intents correctly
        for intent_name, enabled in client.intents:
            if enabled:
                print(f"  ✓ {intent_name}")
        
        # Close the client properly
        await client.close()
    
    async with AsyncExitStack() as stack:
        try:
            # Create a timeout mechanism
            connect_task = asyncio.create_task(client.start(token))
            await asyncio.wait_for(connect_task, timeout=30)
            return True, "All intents are enabled!"
            
        except asyncio.TimeoutError:
            print("❌ ERROR: Connection timed out after 30 seconds")
            return False, "Connection timed out"
            
        except discord.errors.PrivilegedIntentsRequired:
            print("❌ ERROR: Missing privileged intents")
            print("ℹ️  SOLUTION: Enable privileged intents at https://discord.com/developers/applications/")
            print("             1. Go to your application's page")
            print("             2. Navigate to the 'Bot' tab")
            print("             3. Enable the required privileged intents under 'Privileged Gateway Intents'")
            return False, "Missing privileged intents - see console for instructions"
            
        except discord.errors.LoginFailure:
            print("❌ ERROR: Invalid token or authentication failed")
            print("ℹ️  SOLUTION: Check if your token is correct and hasn't been reset")
            return False, "Invalid token or authentication failed"
            
        except Exception as e:
            error_type = type(e).__name__
            print(f"❌ ERROR [{error_type}]: {str(e)}")
            return False, f"Error: {error_type} - {str(e)}"
            
        finally:
            # Ensure client is properly closed to avoid connector warnings
            if not client.is_closed():
                try:
                    await client.close()
                except:
                    pass