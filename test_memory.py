import sys
import logging
from pantheon.memory.mem0_store import MemoryStore

logging.basicConfig(level=logging.DEBUG)

store = MemoryStore()
store.initialize()
store.search("testing connection", limit=1)
