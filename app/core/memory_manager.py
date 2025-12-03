from typing import Dict, List, Any
from app.services.Andy_speech import RefinementMemory

# Enhanced memory management with persistence
class MemoryManager:
    def __init__(self):
        self.user_memories: Dict[str, RefinementMemory] = {}
    
    def get_memory(self, user_id: str) -> RefinementMemory:
        if user_id not in self.user_memories:
            self.user_memories[user_id] = RefinementMemory()
        return self.user_memories[user_id]
    
    def log_refinement_pass(self, user_id: str, original: str, refined: str, score: float = None, notes: List[str] = None):
        memory = self.get_memory(user_id)
        memory.log_pass(original, refined, score, notes)
    
    def get_memory_context(self, user_id: str) -> Dict[str, Any]:
        memory = self.get_memory(user_id)
        return {
            "total_passes": len(memory.history),
            "last_output": memory.last_output(),
            "last_score": memory.last_score(),
            "has_history": bool(memory.history),
            "recent_passes": memory.history[-5:] if memory.history else []
        }

memory_manager = MemoryManager()
