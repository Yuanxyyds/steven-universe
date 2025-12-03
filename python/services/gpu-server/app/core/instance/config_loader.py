"""
Configuration loader and validator.

Per-request instance that lazy-loads only the required task definition,
task action, and model path for a specific task.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass
import yaml

logger = logging.getLogger(__name__)


@dataclass
class TaskDefinition:
    """Pre-defined task template configuration."""
    task_name: str
    description: str
    task_type: str  # "oneoff" or "session"
    task_difficulty: str  # "low" or "high"
    timeout_seconds: int
    metadata: Dict[str, Any]
    model_id: Optional[str] = None  # Optional for non-LLM tasks


@dataclass
class TaskAction:
    """Worker execution configuration for a task."""
    task_name: str
    source_path: str
    dockerfile: str
    docker_image: str
    command: List[str]
    env_vars: Dict[str, str]
    build_args: Dict[str, str]


@dataclass
class ModelPath:
    """Model filesystem path configuration."""
    model_id: str
    path: str
    description: str
    size_gb: float


class ConfigLoader:
    """
    Per-request configuration loader.

    Lazy-loads only the required task definition, task action, and model path
    for a specific task request.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize config loader.

        Args:
            config_dir: Path to config directory. If None, uses default location.
        """
        if config_dir is None:
            # Default: app/config/
            config_dir = Path(__file__).parent.parent.parent / "config"

        self.config_dir = config_dir

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML file.

        Args:
            filename: Name of YAML file in config directory

        Returns:
            Parsed YAML content as dictionary
        """
        file_path = self.config_dir / filename
        try:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.error(f"Config file not found: {file_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return {}

    def get_task_definition(self, task_name: str) -> Optional[TaskDefinition]:
        """
        Load a specific task definition.

        Args:
            task_name: Task name to lookup

        Returns:
            TaskDefinition object or None if not found
        """
        config = self._load_yaml("task_definitions.yaml")

        if task_name not in config:
            logger.warning(f"Task definition not found: {task_name}")
            return None

        task_data = config[task_name]

        return TaskDefinition(
            task_name=task_name,
            description=task_data.get("description", ""),
            task_type=task_data.get("task_type", "oneoff"),
            task_difficulty=task_data.get("task_difficulty", "low"),
            timeout_seconds=task_data.get("timeout_seconds", 300),
            metadata=task_data.get("metadata", {}),
            model_id=task_data.get("model_id")
        )

    def get_task_action(self, task_name: str) -> Optional[TaskAction]:
        """
        Load a specific task action configuration.

        Args:
            task_name: Task name to lookup

        Returns:
            TaskAction object or None if not found
        """
        config = self._load_yaml("task_actions.yaml")

        if task_name not in config:
            logger.warning(f"Task action not found for task: {task_name}")
            return None

        action_data = config[task_name]

        return TaskAction(
            task_name=task_name,
            source_path=action_data.get("source_path", ""),
            dockerfile=action_data.get("dockerfile", ""),
            docker_image=action_data.get("docker_image", ""),
            command=action_data.get("command", []),
            env_vars=action_data.get("env_vars", {}),
            build_args=action_data.get("build_args", {})
        )

    def get_model_path(self, model_id: str) -> Optional[ModelPath]:
        """
        Load a specific model path configuration.

        Args:
            model_id: Model identifier to lookup

        Returns:
            ModelPath object or None if not found
        """
        config = self._load_yaml("model_paths.yaml")

        if model_id not in config:
            logger.debug(f"Model path not found for: {model_id}")
            return None

        path_data = config[model_id]

        return ModelPath(
            model_id=model_id,
            path=path_data.get("path", ""),
            description=path_data.get("description", ""),
            size_gb=path_data.get("size_gb", 0.0)
        )

    def load_task_config(self, task_name: str) -> Tuple[TaskDefinition, TaskAction, Optional[ModelPath]]:
        """
        Load complete configuration for a task.

        Lazy-loads task definition and task action (required),
        and model path (optional, only if model_id is specified in task definition).

        Args:
            task_name: Task name to lookup

        Returns:
            Tuple of (TaskDefinition, TaskAction, ModelPath or None)

        Raises:
            ValueError: If task_name not found or configuration invalid
        """
        # Load task definition
        task_def = self.get_task_definition(task_name)
        if not task_def:
            raise ValueError(f"Task definition not found: {task_name}")

        # Load task action by task_name
        task_action = self.get_task_action(task_name)
        if not task_action:
            raise ValueError(f"Task action not found for task: {task_name}")

        # Load model path (optional, only if model_id is specified)
        model_path = None
        if task_def.model_id:
            model_path = self.get_model_path(task_def.model_id)

        return (task_def, task_action, model_path)

    def resolve_task_config(self, task_name: str, request_overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve task configuration with request overrides.

        Loads task definition and merges with request overrides.

        Args:
            task_name: Task name to lookup
            request_overrides: Dict with optional overrides (task_difficulty, timeout_seconds, metadata, etc.)

        Returns:
            Merged configuration dictionary

        Raises:
            ValueError: If task_name not found
        """
        task_def = self.get_task_definition(task_name)
        if not task_def:
            raise ValueError(f"Task definition not found: {task_name}")

        return {
            'task_type': request_overrides.get('task_type') or task_def.task_type,
            'task_difficulty': request_overrides.get('task_difficulty') or task_def.task_difficulty,
            'model_id': request_overrides.get('model_id') or task_def.model_id,
            'timeout_seconds': request_overrides.get('timeout_seconds') or task_def.timeout_seconds,
            'metadata': {**task_def.metadata, **request_overrides.get('metadata', {})},
        }
