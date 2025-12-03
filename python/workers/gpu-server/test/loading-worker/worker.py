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
    event = {"event": event_type, **data}
    print(json.dumps(event), flush=True)


def main():
    # Get model info from environment
    model_name = os.environ.get("MODEL_NAME", "test-model")
    model_path = os.environ.get("MODEL_PATH", "/models")

    try:
        # CONNECTION event
        emit_event("connection", {
            "status": "connected",
            "worker": "loading-worker",
            "model": model_name
        })

        # WORKER event - starting
        emit_event("worker", {
            "status": "initializing",
            "message": "Initializing GPU..."
        })
        time.sleep(10)

        # Simulate loading model into GPU memory
        emit_event("worker", {
            "status": "loading",
            "message": f"Loading model {model_name} into GPU memory..."
        })

        # Simulate loading time (5 seconds)
        for i in range(1, 6):
            time.sleep(3)
            emit_event("text_delta", {
                "delta": f"Loading progress: {i * 20}%\n"
            })

        # Model loaded
        emit_event("worker", {
            "status": "ready",
            "message": "Model loaded successfully"
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
        emit_event("worker", {
            "status": "cleaning_up",
            "message": "Unloading model from GPU..."
        })
        time.sleep(1)

        emit_event("text_delta", {
            "delta": "GPU memory freed.\n"
        })

        # FINISH event
        emit_event("finish", {
            "status": "completed",
            "message": "Worker completed successfully"
        })

    except Exception as e:
        # Error event
        emit_event("finish", {
            "status": "failed",
            "error": str(e)
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
