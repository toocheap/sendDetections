"""
Configuration settings for the sendDetections package.

Configuration can be set via:
1. Command-line arguments (highest priority)
2. Environment variables
3. Configuration files (YAML/JSON)
4. Default values (lowest priority)
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Set up logger
logger = logging.getLogger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML not installed. YAML configuration files will not be supported.")

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Default configuration paths
DEFAULT_CONFIG_PATHS = [
    PROJECT_ROOT / "senddetections.yml",
    PROJECT_ROOT / "senddetections.yaml",
    PROJECT_ROOT / "senddetections.json",
    Path.home() / ".config" / "senddetections.yml",
    Path.home() / ".config" / "senddetections.yaml",
    Path.home() / ".config" / "senddetections.json",
    Path.home() / ".senddetections.yml",
    Path.home() / ".senddetections.yaml",
    Path.home() / ".senddetections.json",
]

# API settings
API_URL = os.getenv("RF_API_URL", "https://api.recordedfuture.com/collective-insights/detections")

# Default HTTP headers for API requests
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Sample data settings
SAMPLE_DIR = PROJECT_ROOT / "sample"
CSV_PATTERN = "sample_*.csv"
CSV_ENCODING = "utf-8"

# API options defaults
DEFAULT_API_OPTIONS: Dict[str, Any] = {
    "debug": False,
    "summary": True
}

class ConfigManager:
    """
    Configuration manager that handles loading and accessing configuration
    from files, environment variables, and default settings.
    """
    
    def __init__(
        self, 
        config_file: Optional[Union[str, Path]] = None,
        profile: str = "default",
        env_prefix: str = "RF_"
    ):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Optional path to a configuration file
            profile: Configuration profile to use (for multi-environment setups)
            env_prefix: Prefix for environment variables
        """
        self.config_file = config_file
        self.profile = profile
        self.env_prefix = env_prefix
        self.config_data: Dict[str, Any] = {}
        
        # Load configuration
        self._load_config()
        
    def _load_config(self) -> None:
        """Load configuration from the first available configuration file."""
        if self.config_file:
            # If a specific config file was provided, try to load it
            config_path = Path(self.config_file)
            if not config_path.exists():
                logger.warning(f"Specified config file not found: {config_path}")
            else:
                self._load_config_file(config_path)
        else:
            # Try loading from default locations
            for path in DEFAULT_CONFIG_PATHS:
                if path.exists():
                    logger.debug(f"Loading configuration from: {path}")
                    self._load_config_file(path)
                    break
    
    def _load_config_file(self, config_path: Path) -> None:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to configuration file (YAML or JSON)
        """
        try:
            extension = config_path.suffix.lower()
            
            if extension in ['.yml', '.yaml']:
                if not YAML_AVAILABLE:
                    logger.warning("Cannot load YAML config - PyYAML not installed")
                    return
                
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
            elif extension == '.json':
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            else:
                logger.warning(f"Unsupported config file format: {extension}")
                return
            
            if not config_data:
                logger.warning(f"Empty configuration file: {config_path}")
                return
                
            # Handle profiles
            if isinstance(config_data, dict) and 'profiles' in config_data:
                profiles = config_data.get('profiles', {})
                if self.profile in profiles:
                    self.config_data = profiles[self.profile]
                    logger.debug(f"Loaded configuration profile: {self.profile}")
                else:
                    logger.warning(f"Profile '{self.profile}' not found in config file")
                    if 'default' in profiles:
                        self.config_data = profiles['default']
                        logger.debug("Loaded 'default' profile as fallback")
            else:
                # No profiles, use entire config
                self.config_data = config_data
                
            logger.debug(f"Successfully loaded configuration from {config_path}")
            
        except Exception as e:
            logger.warning(f"Error loading configuration from {config_path}: {str(e)}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with fallback to environment and default.
        
        Args:
            key: Configuration key
            default: Default value if not found in config or environment
            
        Returns:
            Configuration value
        """
        # Check environment variables first (highest priority)
        env_key = f"{self.env_prefix}{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return self._convert_value(env_value)
        
        # Check in loaded config
        if key in self.config_data:
            return self.config_data[key]
        
        # Fall back to default
        return default
    
    def _convert_value(self, value: str) -> Any:
        """
        Convert string values from environment variables to appropriate types.
        
        Args:
            value: String value from environment variable
            
        Returns:
            Converted value (bool, int, float, or original string)
        """
        # Convert to boolean if it matches true/false
        lower_val = value.lower()
        if lower_val in ['true', 'yes', '1']:
            return True
        if lower_val in ['false', 'no', '0']:
            return False
        
        # Try to convert to number
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            # Return as string if not a number
            return value
            
    def get_dict(self, prefix: str = "") -> Dict[str, Any]:
        """
        Get all configuration values with a certain prefix as a dictionary.
        
        Args:
            prefix: Optional prefix filter for keys
            
        Returns:
            Dictionary of configuration values
        """
        result = {}
        
        # Get keys from config file
        for key, value in self.config_data.items():
            if key.startswith(prefix):
                result[key] = value
        
        # Override with environment variables
        for env_key, env_value in os.environ.items():
            if env_key.startswith(self.env_prefix):
                key = env_key[len(self.env_prefix):].lower()
                if prefix and not key.startswith(prefix.lower()):
                    continue
                result[key] = self._convert_value(env_value)
                
        return result


# Create a default config manager instance for package-level access
config_manager = ConfigManager()

# Helper functions to access configuration
def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value."""
    return config_manager.get(key, default)

def get_api_url() -> str:
    """Get the API URL from configuration or environment."""
    return get_config("api_url", API_URL)

def get_api_options() -> Dict[str, Any]:
    """Get API options from configuration."""
    options = DEFAULT_API_OPTIONS.copy()
    
    # Override with values from config
    config_options = config_manager.get_dict("api_options_")
    for key, value in config_options.items():
        # Remove the prefix and add to options
        option_key = key.replace("api_options_", "")
        options[option_key] = value
    
    return options