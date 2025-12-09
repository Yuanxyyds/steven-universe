#!/usr/bin/env python3
"""
GPU Loading Worker - Test Worker for GPU Service

Simulates loading and unloading a model from GPU memory.
Emits structured JSON events that the GPU service parses.
"""

import json
import sys
import time
import os

def emit_event(event_type: str, data: dict):
    """Emit a structured JSON event to stdout."""
    event = {"type": event_type, "data": data}
    print(json.dumps(event), flush=True)


def main():
    # Get model info from environment
    model_name = os.environ.get("MODEL_NAME", "test-model")
    model_path = os.environ.get("MODEL_PATH", "/models")

    try:
        # CONNECTED event (was CONNECTION)
        emit_event("connected", {
            "status": "connected",
            "worker": "loading-worker",
            "model": model_name
        })

        # LOGS event - starting (was WORKER)
        emit_event("logs", {
            "log": "Initializing GPU...",
            "level": "info"
        })
        time.sleep(10)

        # Simulate loading model into GPU memory
        emit_event("logs", {
            "log": f"Loading model {model_name} into GPU memory...",
            "level": "info"
        })

        # Simulate loading time (5 seconds)
        for i in range(1, 6):
            time.sleep(3)
            emit_event("text_delta", {
                "delta": f"Loading progress: {i * 20}%\n"
            })

        # Model loaded
        emit_event("logs", {
            "log": "Model loaded successfully",
            "level": "info"
        })

        # Simulate some GPU computation
        emit_event("text_delta", {
            "delta": "\nPerforming GPU computation...\n"
        })
        time.sleep(2)

        emit_event("text", {
            "content": f"Model {model_name} computation complete!\nGPU memory allocated: ~2GB\n"
        })

        # Simulate unloading model
        emit_event("logs", {
            "log": "Unloading model from GPU...",
            "level": "info"
        })
        time.sleep(1)

        emit_event("text_delta", {
            "delta": "GPU memory freed.\n"
        })

        # COMPLETED event (was FINISH)
        emit_event("completed", {
            "status": "completed"
        })

    except Exception as e:
        # Error event
        emit_event("completed", {
            "status": "failed",
            "error": str(e)
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
