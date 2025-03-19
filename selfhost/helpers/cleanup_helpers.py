import logging
import datetime
import asyncio
from discord.ext import tasks

# Configure logging
logger = logging.getLogger("openshape.cleanup")

class CleanupTasks:
    """Manages scheduled cleanup tasks for the bot"""
    def __init__(self, bot):
        self.bot = bot
        self.timeout_minutes = bot.conversation_timeout if hasattr(bot, "conversation_timeout") else 30
        
    def start_tasks(self):
        """Start all scheduled tasks"""
        self.conversation_cleanup.start()
        logger.info(f"Started conversation cleanup task (timeout: {self.timeout_minutes} minutes)")
        
    def stop_tasks(self):
        """Stop all scheduled tasks"""
        if self.conversation_cleanup.is_running():
            self.conversation_cleanup.cancel()
            logger.info("Stopped conversation cleanup task")
    
    @tasks.loop(minutes=5)  # Check every 5 minutes
    async def conversation_cleanup(self):
        """Task to clean up old conversations that haven't been active recently"""
        if not hasattr(self.bot, "channel_conversations"):
            return
        
        current_time = datetime.datetime.now()
        channels_to_cleanup = []
        
        # Find channels with inactive conversations
        for channel_id, conversation in self.bot.channel_conversations.items():
            if not conversation:
                continue
                
            # Get timestamp from last message
            try:
                last_message = conversation[-1]
                last_timestamp = last_message.get("timestamp")
                
                if last_timestamp:
                    last_time = datetime.datetime.fromisoformat(last_timestamp)
                    time_diff = current_time - last_time
                    
                    # If conversation is older than timeout, mark for cleanup
                    if time_diff.total_seconds() > (self.timeout_minutes * 60):
                        channels_to_cleanup.append(channel_id)
                        logger.info(f"Cleaning up conversation in channel {channel_id} - inactive for {time_diff.total_seconds()/60:.1f} minutes")
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"Error processing conversation timestamps: {e}")
        
        # Clean up the inactive conversations
        for channel_id in channels_to_cleanup:
            del self.bot.channel_conversations[channel_id]
            
    @conversation_cleanup.before_loop
    async def before_conversation_cleanup(self):
        """Wait until the bot is ready before starting the cleanup task"""
        await self.bot.wait_until_ready()


class FileCleanup:
    """Handles cleaning up temp files and other maintenance tasks"""
    def __init__(self, bot):
        self.bot = bot
        self.temp_dir = bot.data_dir + "/temp_audio" if hasattr(bot, "data_dir") else "temp_audio"
        
    async def cleanup_temp_files(self, max_age_hours=24):
        """Clean up temporary files older than the specified age"""
        import os
        from pathlib import Path
        
        try:
            # Get current time
            current_time = datetime.datetime.now()
            count = 0
            
            # Check all files in temp directory
            for file_path in Path(self.temp_dir).glob('*.mp3'):
                try:
                    # Get file creation/modification time
                    file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                    age = current_time - file_time
                    
                    # If file is older than max age, delete it
                    if age.total_seconds() > (max_age_hours * 3600):
                        os.remove(file_path)
                        count += 1
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    
            if count > 0:
                logger.info(f"Cleaned up {count} temporary audio files older than {max_age_hours} hours")
                
        except Exception as e:
            logger.error(f"Error in temp file cleanup: {e}")
    
    @tasks.loop(hours=6)  # Run every 6 hours
    async def scheduled_file_cleanup(self):
        """Run file cleanup on a schedule"""
        await self.cleanup_temp_files()
        
    def start_tasks(self):
        """Start all cleanup tasks"""
        self.scheduled_file_cleanup.start()
        logger.info("Started scheduled file cleanup task")
        
    def stop_tasks(self):
        """Stop all cleanup tasks"""
        if self.scheduled_file_cleanup.is_running():
            self.scheduled_file_cleanup.cancel()
            logger.info("Stopped scheduled file cleanup task")


class OpenShapeCleanup:
    """Main class to manage all cleanup operations"""
    def __init__(self, bot):
        self.bot = bot
        self.conversation_cleanup = CleanupTasks(bot)
        self.file_cleanup = FileCleanup(bot)
        
    def start_all_tasks(self):
        """Start all cleanup tasks"""
        self.conversation_cleanup.start_tasks()
        self.file_cleanup.start_tasks()
        
    def stop_all_tasks(self):
        """Stop all cleanup tasks"""
        self.conversation_cleanup.stop_tasks()
        self.file_cleanup.stop_tasks()
        
    async def run_all_cleanups(self):
        """Run all cleanup tasks immediately"""
        await self.conversation_cleanup.conversation_cleanup()
        await self.file_cleanup.cleanup_temp_files()


# Utility function to initialize cleanup
def setup_cleanup(bot):
    cleanup = OpenShapeCleanup(bot)
    cleanup.start_all_tasks()
    return cleanup