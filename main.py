import json
import os
from datetime import datetime

import yaml
from flask import Flask
from loguru import logger

from src.workflow import Workflow

log_file = f"logs/{datetime.now().strftime('%Y-%m-%d')}.log"
logger.add(log_file, rotation="1 day", mode="a")

app = Flask(__name__)

def read_config(config_path):
    """
    Read and parse a YAML configuration file.
    
    Args:
        config_path (str): Path to the YAML configuration file
        
    Returns:
        dict: Parsed configuration data
    """
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
    except Exception as e:
        logger.error(f"Unexpected error reading configuration: {e}")
    return None

cfg = read_config(os.path.join("configs", "config.yaml"))
logger.info(f"\n{json.dumps(cfg, indent=4)}")

@app.route('/fetch', methods=['GET'])
def fetch():
    workflow = Workflow(cfg)
    return workflow.run()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=33678)