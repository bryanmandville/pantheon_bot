import asyncio
import logging
from pantheon.memory.mem0_store import MemoryStore
from pantheon.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

async def verify_memory():
    print(f"--- Verifying Memory (Ollama: {settings.ollama_model}, Qdrant: {settings.qdrant_host}) ---")

    # 1. Initialize
    store = MemoryStore()
    try:
        await asyncio.to_thread(store.initialize)
        print("✅ Memory store initialized (connected to Qdrant).")
    except Exception as e:
        print(f"❌ Failed to initialize memory store: {e}")
        return

    # 2. Add Memory
    test_fact = "The user prefers Python over JavaScript."
    print(f"\nAdding memory: '{test_fact}'")
    try:
        await asyncio.to_thread(store.add, test_fact, metadata={"source": "verification_script"})
        print("✅ Memory added.")
    except Exception as e:
        print(f"❌ Failed to add memory: {e}")
        return

    # 3. Search Memory
    query = "preferred language"
    print(f"\nSearching for: '{query}'")
    try:
        results = await asyncio.to_thread(store.search, query)
        print(f"Results found: {len(results)}")
        for r in results:
            print(f"- {r}")
        
        if any("Python" in str(r) for r in results):
            print("✅ Meaningful result found.")
        else:
            print("⚠️  No meaningful result found (embedding model issue?)")

    except Exception as e:
        print(f"❌ Failed to search memory: {e}")

if __name__ == "__main__":
    asyncio.run(verify_memory())
