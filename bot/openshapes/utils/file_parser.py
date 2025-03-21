import discord
import os
import logging
from typing import Optional

logger = logging.getLogger("openshape")

class FileParser:
    async def process_attachments(self, message: discord.Message) -> str:
        if not message.attachments:
            return ""
        
        result = []
        
        for attachment in message.attachments:
            file_content = await self._extract_file_content(attachment)
            if file_content:
                result.append(f"File: {attachment.filename}\n{file_content}")
        
        if result:
            return "\n\n".join(result)
        else:
            return ""
    
    async def _extract_file_content(self, attachment: discord.Attachment) -> Optional[str]:
        if attachment.size > 4 * 1024 * 1024:  # 4MB limit
            return f"[File too large to process: {attachment.filename}]"
        
        file_ext = os.path.splitext(attachment.filename)[1].lower()
        
        if file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.csv', '.xml', '.yml', '.yaml']:
            try:
                content = await attachment.read()
                text_content = content.decode('utf-8')
                
                # Truncate if too long
                if len(text_content) > 8000:
                    text_content = text_content[:8000] + "\n[Content truncated due to length...]"
                    
                return text_content
            except Exception as e:
                logger.error(f"Error processing file {attachment.filename}: {e}")
                return f"[Error reading file: {attachment.filename}]"
        elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            return f"[Image: {attachment.filename}]"
        elif file_ext in ['.mp3', '.wav', '.ogg', '.m4a']:
            return f"[Audio: {attachment.filename}]"
        elif file_ext in ['.mp4', '.webm', '.mov']:
            return f"[Video: {attachment.filename}]"
        elif file_ext in ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls']:
            return f"[Document: {attachment.filename} - Cannot extract text from this file type]"
        else:
            return f"[Unsupported file type: {attachment.filename}]"
