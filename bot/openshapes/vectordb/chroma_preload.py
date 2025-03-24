"""
ChromaDB model preloading module.
This module provides functionality to preload the ChromaDB embedding model during bot startup.
"""

import logging
import asyncio

logger = logging.getLogger("openshape.chroma_integration")

async def preload_chromadb_model(memory_manager):
    """
    Preloads the ChromaDB embedding model by making a small test operation.
    This ensures the model is downloaded during startup rather than during the first memory operation.
    
    Args:
        memory_manager: The memory manager instance containing the ChromaDB collection
    """
    try:
        logger.info("Preloading ChromaDB embedding model...")
        
        await asyncio.sleep(5)
        
        collection = memory_manager.collection
        
        try:
            collection.query(
                query_texts=["initialization test"],
                n_results=1
            )
            logger.info("ChromaDB embedding model preloaded successfully")
        except Exception as e:
            logger.error(f"Error during preload query: {e}")
            
    except Exception as e:
        logger.error(f"Failed to preload ChromaDB model: {e}")