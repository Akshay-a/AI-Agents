"""
Context Manager for Intelligent LLM Context Optimization

Handles context caching, pruning, and optimization to reduce API costs
while maintaining sufficient context for effective code generation.
"""

import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from pathlib import Path


@dataclass
class ContextItem:
    """Individual context item with metadata"""
    content: str
    item_type: str  # 'user_requirement', 'legacy_code', 'search_result', 'generated_code', etc.
    priority: int  # 1-10, higher = more important
    timestamp: datetime
    source: str  # Where this context came from
    tokens_estimate: int  # Rough token estimate
    fingerprint: str  # Hash for deduplication
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass 
class ContextWindow:
    """Complete context window for LLM call"""
    items: List[ContextItem]
    total_tokens: int
    fingerprint: str  # Hash of entire context
    created_at: datetime
    
    def to_prompt(self) -> str:
        """Convert context window to formatted prompt"""
        sections = {
            'user_requirement': [],
            'legacy_code': [],
            'search_result': [],
            'generated_code': [],
            'validation_result': [],
            'other': []
        }
        
        # Group items by type
        for item in sorted(self.items, key=lambda x: x.priority, reverse=True):
            section = sections.get(item.item_type, sections['other'])
            section.append(item)
        
        prompt_parts = []
        
        # Add user requirements first
        if sections['user_requirement']:
            prompt_parts.append("## User Requirements:")
            for item in sections['user_requirement']:
                prompt_parts.append(f"- {item.content}")
        
        # Add legacy code context
        if sections['legacy_code']:
            prompt_parts.append("\n## Legacy Code Context:")
            for item in sections['legacy_code']:
                prompt_parts.append(f"### {item.source}")
                prompt_parts.append(f"```\n{item.content}\n```")
        
        # Add search results
        if sections['search_result']:
            prompt_parts.append("\n## Relevant Code Examples:")
            for item in sections['search_result']:
                prompt_parts.append(f"### {item.source}")
                prompt_parts.append(f"```\n{item.content}\n```")
        
        # Add previous attempts
        if sections['generated_code']:
            prompt_parts.append("\n## Previous Code Attempts:")
            for item in sections['generated_code']:
                prompt_parts.append(f"### {item.source}")
                prompt_parts.append(f"```\n{item.content}\n```")
        
        # Add validation results
        if sections['validation_result']:
            prompt_parts.append("\n## Validation Feedback:")
            for item in sections['validation_result']:
                prompt_parts.append(f"- {item.content}")
        
        return "\n".join(prompt_parts)


class ContextCache:
    """Cache for context windows and API responses"""
    
    def __init__(self, cache_dir: str = "/tmp/code_generation_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # In-memory cache for quick access
        self.memory_cache: Dict[str, Tuple[ContextWindow, str]] = {}  # fingerprint -> (context, response)
        self.cache_timeout = timedelta(hours=1)  # Cache expires after 1 hour
    
    def get_cached_response(self, context_fingerprint: str) -> Optional[str]:
        """Get cached LLM response for context fingerprint"""
        # Check memory cache first
        if context_fingerprint in self.memory_cache:
            context, response = self.memory_cache[context_fingerprint]
            if datetime.now() - context.created_at < self.cache_timeout:
                self.logger.info(f"Cache hit (memory) for context: {context_fingerprint[:8]}")
                return response
            else:
                # Expired, remove from memory
                del self.memory_cache[context_fingerprint]
        
        # Check disk cache
        cache_file = self.cache_dir / f"{context_fingerprint}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                created_at = datetime.fromisoformat(cache_data['created_at'])
                if datetime.now() - created_at < self.cache_timeout:
                    response = cache_data['response']
                    self.logger.info(f"Cache hit (disk) for context: {context_fingerprint[:8]}")
                    return response
                else:
                    # Expired, remove file
                    cache_file.unlink()
            except Exception as e:
                self.logger.warning(f"Error reading cache file: {e}")
        
        return None
    
    def cache_response(self, context: ContextWindow, response: str) -> None:
        """Cache LLM response for future use"""
        try:
            # Store in memory cache
            self.memory_cache[context.fingerprint] = (context, response)
            
            # Store in disk cache
            cache_data = {
                'context_fingerprint': context.fingerprint,
                'response': response,
                'created_at': context.created_at.isoformat(),
                'total_tokens': context.total_tokens
            }
            
            cache_file = self.cache_dir / f"{context.fingerprint}.json"
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            self.logger.info(f"Cached response for context: {context.fingerprint[:8]}")
            
        except Exception as e:
            self.logger.warning(f"Error caching response: {e}")
    
    def cleanup_expired(self) -> None:
        """Clean up expired cache entries"""
        try:
            now = datetime.now()
            
            # Clean memory cache
            expired_keys = [
                key for key, (context, _) in self.memory_cache.items()
                if now - context.created_at > self.cache_timeout
            ]
            for key in expired_keys:
                del self.memory_cache[key]
            
            # Clean disk cache
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                    
                    created_at = datetime.fromisoformat(cache_data['created_at'])
                    if now - created_at > self.cache_timeout:
                        cache_file.unlink()
                        
                except Exception as e:
                    self.logger.warning(f"Error cleaning cache file {cache_file}: {e}")
            
            self.logger.info(f"Cache cleanup complete. Removed {len(expired_keys)} memory entries")
            
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {e}")


class ContextManager:
    """Intelligent context management for LLM calls"""
    
    def __init__(self, max_tokens: int = 32000, cache_dir: str = "/tmp/code_generation_cache"):
        self.max_tokens = max_tokens
        self.reserved_tokens = 4000  # Reserve for response generation
        self.available_tokens = max_tokens - self.reserved_tokens
        
        self.cache = ContextCache(cache_dir)
        self.logger = logging.getLogger(__name__)
        
        # Context item prioritization weights
        self.priority_weights = {
            'user_requirement': 10,
            'validation_result': 9,
            'legacy_code': 8,
            'search_result': 7,
            'generated_code': 6,
            'other': 5
        }
    
    def create_context_item(self, content: str, item_type: str, source: str, 
                          priority: Optional[int] = None) -> ContextItem:
        """Create a context item with automatic metadata"""
        if priority is None:
            priority = self.priority_weights.get(item_type, 5)
        
        # Estimate tokens (rough approximation: 1 token ≈ 3.5 characters)
        tokens_estimate = len(content) // 3.5
        
        # Create fingerprint for deduplication
        fingerprint = hashlib.md5(f"{content}{item_type}{source}".encode()).hexdigest()
        
        return ContextItem(
            content=content,
            item_type=item_type,
            priority=priority,
            timestamp=datetime.now(),
            source=source,
            tokens_estimate=int(tokens_estimate),
            fingerprint=fingerprint
        )
    
    def build_context_window(self, items: List[ContextItem]) -> ContextWindow:
        """Build optimized context window from items"""
        # Deduplicate items by fingerprint
        unique_items = {}
        for item in items:
            if item.fingerprint not in unique_items:
                unique_items[item.fingerprint] = item
            else:
                # Keep the one with higher priority or more recent timestamp
                existing = unique_items[item.fingerprint]
                if item.priority > existing.priority or \
                   (item.priority == existing.priority and item.timestamp > existing.timestamp):
                    unique_items[item.fingerprint] = item
        
        deduplicated_items = list(unique_items.values())
        
        # Sort by priority and recency
        sorted_items = sorted(
            deduplicated_items,
            key=lambda x: (x.priority, x.timestamp.timestamp()),
            reverse=True
        )
        
        # Select items within token limit
        selected_items = []
        total_tokens = 0
        
        for item in sorted_items:
            if total_tokens + item.tokens_estimate <= self.available_tokens:
                selected_items.append(item)
                total_tokens += item.tokens_estimate
            else:
                # Try to fit partial content if it's important
                if item.priority >= 8 and total_tokens < self.available_tokens * 0.9:
                    remaining_tokens = self.available_tokens - total_tokens
                    remaining_chars = int(remaining_tokens * 3.5)
                    
                    if remaining_chars > 100:  # Only if we can fit meaningful content
                        truncated_content = item.content[:remaining_chars] + "...[truncated]"
                        truncated_item = ContextItem(
                            content=truncated_content,
                            item_type=item.item_type,
                            priority=item.priority,
                            timestamp=item.timestamp,
                            source=f"{item.source} (truncated)",
                            tokens_estimate=remaining_tokens,
                            fingerprint=f"{item.fingerprint}_truncated"
                        )
                        selected_items.append(truncated_item)
                        total_tokens = self.available_tokens
                        break
        
        # Create context window fingerprint
        content_hash = hashlib.md5(
            "".join([item.fingerprint for item in selected_items]).encode()
        ).hexdigest()
        
        context_window = ContextWindow(
            items=selected_items,
            total_tokens=total_tokens,
            fingerprint=content_hash,
            created_at=datetime.now()
        )
        
        self.logger.info(
            f"Built context window: {len(selected_items)} items, "
            f"{total_tokens} tokens, fingerprint: {content_hash[:8]}"
        )
        
        return context_window
    
    def get_or_create_context(self, items: List[ContextItem]) -> Tuple[ContextWindow, Optional[str]]:
        """Get cached context or create new one. Returns (context, cached_response)"""
        context_window = self.build_context_window(items)
        cached_response = self.cache.get_cached_response(context_window.fingerprint)
        
        return context_window, cached_response
    
    def cache_llm_response(self, context: ContextWindow, response: str) -> None:
        """Cache LLM response for this context"""
        self.cache.cache_response(context, response)
    
    def cleanup_cache(self) -> None:
        """Clean up expired cache entries"""
        self.cache.cleanup_expired()
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get context manager statistics"""
        return {
            'max_tokens': self.max_tokens,
            'available_tokens': self.available_tokens,
            'reserved_tokens': self.reserved_tokens,
            'cache_size': len(self.cache.memory_cache),
            'cache_timeout_hours': self.cache.cache_timeout.total_seconds() / 3600
        } 