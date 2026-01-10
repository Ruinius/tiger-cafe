from app.utils.document_queue_v2 import DocumentQueue

# Global singleton instance
# Initialized in main.py startup event (or lazily here, but we want control)
# Ideally we instantiate on import or startup.
# We'll instantiate on import for simplicity as it starts a thread (daemon).
# If we need deferred startup, we can make it None and init later.
# For now, let's instantiate it so routers can import 'queue_service' directly.

queue_service = DocumentQueue()


def get_queue_service() -> DocumentQueue:
    return queue_service
