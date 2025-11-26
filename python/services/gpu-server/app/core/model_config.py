"""
Model preset configuration loader and validator.

Loads model_presets.yaml and provides lookup functions for
model_id + task_preset combinations.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
import yaml

logger = logging.getLogger(__name__)


class ModelPreset:
    """Single model preset configuration."""

    def __init__(
        self,
        model_id: str,
        task_preset: str,
        docker_image: str,
        command: List[str],
        env_vars: Dict[str, str]
    ):
        self.model_id = model_id
        self.task_preset = task_preset
        self.docker_image = docker_image
        self.command = command
        self.env_vars = env_vars

    def __repr__(self):
        return f"ModelPreset({self.model_id}/{self.task_preset}, image={self.docker_image})"


class ModelConfigManager:
    """
    Manages model preset configurations from YAML.

    Provides validation and lookup for model_id + task_preset combinations.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize model config manager.

        Args:
            config_path: Path to model_presets.yaml. If None, uses default location.
        """
        if config_path is None:
            # Default: app/config/model_presets.yaml
            config_path = Path(__file__).parent.parent / "config" / "model_presets.yaml"

        self.config_path = config_path
        self._presets: Dict[str, Dict[str, ModelPreset]] = {}
        self._loaded = False

    def load(self):
        """Load and parse model_presets.yaml."""
        if self._loaded:
            return

        logger.info(f"Loading model presets from {self.config_path}")

        if not self.config_path.exists():
            raise FileNotFoundError(f"Model presets config not found: {self.config_path}")

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            if not config or 'models' not in config:
                raise ValueError("Invalid config: missing 'models' key")

            # Parse presets
            for model_id, presets in config['models'].items():
                self._presets[model_id] = {}

                for task_preset, preset_config in presets.items():
                    # Validate required fields
                    if 'docker_image' not in preset_config:
                        raise ValueError(f"Missing 'docker_image' for {model_id}/{task_preset}")
                    if 'command' not in preset_config:
                        raise ValueError(f"Missing 'command' for {model_id}/{task_preset}")

                    # Create ModelPreset object
                    preset = ModelPreset(
                        model_id=model_id,
                        task_preset=task_preset,
                        docker_image=preset_config['docker_image'],
                        command=preset_config['command'],
                        env_vars=preset_config.get('env_vars', {})
                    )

                    self._presets[model_id][task_preset] = preset
                    logger.debug(f"Loaded preset: {preset}")

            self._loaded = True
            logger.info(f"Successfully loaded {self.get_preset_count()} model presets")

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load model presets: {e}")
            raise

    def get_preset(self, model_id: str, task_preset: str) -> Optional[ModelPreset]:
        """
        Get model preset configuration.

        Args:
            model_id: Model identifier (e.g., "llama-7b")
            task_preset: Task preset (e.g., "inference")

        Returns:
            ModelPreset if found, None otherwise
        """
        if not self._loaded:
            self.load()

        if model_id not in self._presets:
            logger.warning(f"Model ID not found: {model_id}")
            return None

        if task_preset not in self._presets[model_id]:
            logger.warning(f"Task preset not found: {model_id}/{task_preset}")
            return None

        return self._presets[model_id][task_preset]

    def validate_preset(self, model_id: str, task_preset: str) -> bool:
        """
        Check if model_id + task_preset combination exists.

        Args:
            model_id: Model identifier
            task_preset: Task preset

        Returns:
            True if valid, False otherwise
        """
        return self.get_preset(model_id, task_preset) is not None

    def get_available_models(self) -> List[str]:
        """
        Get list of all available model IDs.

        Returns:
            List of model_id strings
        """
        if not self._loaded:
            self.load()
        return list(self._presets.keys())

    def get_available_presets(self, model_id: str) -> List[str]:
        """
        Get list of available task presets for a model.

        Args:
            model_id: Model identifier

        Returns:
            List of task preset strings, empty if model not found
        """
        if not self._loaded:
            self.load()

        if model_id not in self._presets:
            return []

        return list(self._presets[model_id].keys())

    def get_preset_count(self) -> int:
        """
        Get total number of presets loaded.

        Returns:
            Total preset count across all models
        """
        if not self._loaded:
            return 0

        total = 0
        for model_presets in self._presets.values():
            total += len(model_presets)
        return total

    def reload(self):
        """Reload configuration from disk."""
        self._presets.clear()
        self._loaded = False
        self.load()
        logger.info("Model presets reloaded")


# Global model config manager instance
model_config_manager = ModelConfigManager()
