import discord
import os
import csv
from io import StringIO

class FileParser:
    """Helper class to parse uploaded files and format them for the prompt."""
    
    def __init__(self, max_file_size_kb=500):
        self.max_file_size_kb = max_file_size_kb  # Maximum file size in KB
    
    async def process_attachments(self, message):
        """Process any attachments in the message and return formatted content."""
        if not message.attachments:
            return None
        
        file_contents = []
        
        for attachment in message.attachments:
            # Check file size
            if attachment.size > (self.max_file_size_kb * 1024):
                continue  # Skip files that are too large
                
            # Check file extension
            file_name = attachment.filename.lower()
            if file_name.endswith('.txt'):
                content = await self._process_text_file(attachment)
                if content:
                    file_contents.append(f"[EXTRA INFORMATION: THIS IS THE CONTENTS OF A TEXT FILE YOU HAVE BEEN GIVEN]\n{content}\n[/EXTRA INFORMATION: THIS IS THE CONTENTS OF A TEXT FILE YOU HAVE BEEN GIVEN]")
            
            elif file_name.endswith('.csv'):
                content = await self._process_csv_file(attachment)
                if content:
                    file_contents.append(f"[EXTRA INFORMATION: THIS IS THE CONTENTS OF A CSV FILE YOU HAVE BEEN GIVEN]\n{content}\n[/EXTRA INFORMATION: THIS IS THE CONTENTS OF A CSV FILE YOU HAVE BEEN GIVEN]")
        
        if file_contents:
            return "\n\n".join(file_contents)
        return None
    
    async def _process_text_file(self, attachment):
        """Process a text file attachment."""
        try:
            content = await attachment.read()
            # Convert bytes to string, handle potential encoding issues
            text_content = content.decode('utf-8', errors='replace')
            return text_content
        except Exception as e:
            print(f"Error processing text file: {e}")
            return None
    
    async def _process_csv_file(self, attachment):
        """Process a CSV file attachment and return it as formatted text."""
        try:
            content = await attachment.read()
            text_content = content.decode('utf-8', errors='replace')
            
            # Parse CSV and convert to readable format
            csv_reader = csv.reader(StringIO(text_content))
            formatted_rows = []
            
            for row in csv_reader:
                formatted_rows.append(','.join(row))
            
            return '\n'.join(formatted_rows)
        except Exception as e:
            print(f"Error processing CSV file: {e}")
            return None