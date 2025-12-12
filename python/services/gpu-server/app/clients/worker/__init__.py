"""
Worker client package - GPU worker protocol and implementations.
"""

from app.clients.worker.base import GPUWorkerProtocol
from app.clients.worker.registry import worker_client_registry, WorkerClientRegistry

__all__ = [
    'GPUWorkerProtocol',
    'worker_client_registry',
    'WorkerClientRegistry',
]
