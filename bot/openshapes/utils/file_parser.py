import discord
import os
import logging
from typing import Optional, List, Set
from enum import Enum, auto

logger = logging.getLogger("openshape")

class FileType(Enum):
    TEXT = auto()
    IMAGE = auto()
    AUDIO = auto()
    VIDEO = auto()
    DOCUMENT = auto()
    UNKNOWN = auto()

class FileProcessingError(Exception):
    def __init__(self, message: str, filename: str):
        self.filename = filename
        self.message = message
        super().__init__(f"{message}: {filename}")

class FileExtensionManager:
    TEXT_EXTENSIONS: Set[str] = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.csv', '.xml', '.yml', '.yaml'}
    IMAGE_EXTENSIONS: Set[str] = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    AUDIO_EXTENSIONS: Set[str] = {'.mp3', '.wav', '.ogg', '.m4a'}
    VIDEO_EXTENSIONS: Set[str] = {'.mp4', '.webm', '.mov'}
    DOCUMENT_EXTENSIONS: Set[str] = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls'}
    
    @classmethod
    def get_file_type(cls, extension: str) -> FileType:
        extension = extension.lower()
        
        if extension in cls.TEXT_EXTENSIONS:
            return FileType.TEXT
        elif extension in cls.IMAGE_EXTENSIONS:
            return FileType.IMAGE
        elif extension in cls.AUDIO_EXTENSIONS:
            return FileType.AUDIO
        elif extension in cls.VIDEO_EXTENSIONS:
            return FileType.VIDEO
        elif extension in cls.DOCUMENT_EXTENSIONS:
            return FileType.DOCUMENT
        else:
            return FileType.UNKNOWN
            
    @classmethod
    def get_extension(cls, filename: str) -> str:
        return os.path.splitext(filename)[1].lower()

class TextProcessor:
    @staticmethod
    def truncate_long_text(text: str, max_length: int = 8000) -> str:
        if len(text) <= max_length:
            return text
            
        return text[:max_length] + "\n[Content truncated due to length...]"

class FileParser:
    MAX_FILE_SIZE = 4 * 1024 * 1024  # 4MB
    MAX_TEXT_LENGTH = 8000
    
    def __init__(self):
        self.extension_manager = FileExtensionManager()
        
    async def process_attachments(self, message: discord.Message) -> str:
        if not message.attachments:
            return ""
        
        result: List[str] = []
        
        for attachment in message.attachments:
            try:
                file_content = await self._extract_file_content(attachment)
                if file_content:
                    result.append(f"File: {attachment.filename}\n{file_content}")
            except FileProcessingError as e:
                logger.warning(f"File processing error: {e}")
                result.append(f"File: {attachment.filename}\n[Error: {e.message}]")
        
        return "\n\n".join(result) if result else ""
    
    async def _extract_file_content(self, attachment: discord.Attachment) -> Optional[str]:
        if attachment.size > self.MAX_FILE_SIZE:
            raise FileProcessingError("File too large to process", attachment.filename)
        
        file_ext = self.extension_manager.get_extension(attachment.filename)
        file_type = self.extension_manager.get_file_type(file_ext)
        
        if file_type == FileType.TEXT:
            return await self._process_text_file(attachment)
        elif file_type == FileType.IMAGE:
            return f"[Image: {attachment.filename}]"
        elif file_type == FileType.AUDIO:
            return f"[Audio: {attachment.filename}]"
        elif file_type == FileType.VIDEO:
            return f"[Video: {attachment.filename}]"
        elif file_type == FileType.DOCUMENT:
            return f"[Document: {attachment.filename} - Cannot extract text from this file type]"
        else:
            return f"[Unsupported file type: {attachment.filename}]"
            
    async def _process_text_file(self, attachment: discord.Attachment) -> str:
        try:
            content = await attachment.read()
            text_content = content.decode('utf-8')
            return TextProcessor.truncate_long_text(text_content, self.MAX_TEXT_LENGTH)
        except UnicodeDecodeError:
            raise FileProcessingError("File is not valid UTF-8 text", attachment.filename)
        except Exception as e:
            logger.error(f"Error processing file {attachment.filename}: {e}")
            raise FileProcessingError(f"Error reading file: {str(e)}", attachment.filename)
