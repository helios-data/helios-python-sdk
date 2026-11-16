from pydantic import BaseModel
import os

# Only if you have the config.py setup with a Config(BaseModel) class in your project root folder
# You can load the config by passing in your Config class via:
# config = load_pydantic_config(Config)
def load_pydantic_config[T: BaseModel](config_class: type[T]) -> T:
    config_file_path = os.getenv("PYDANTIC_CONFIG_PATH")
    if not config_file_path:
        raise ValueError("PYDANTIC_CONFIG_PATH environment variable is not set or empty.")

    with open(config_file_path, "r", encoding="utf-8") as f:
        return config_class.model_validate_json(f.read())