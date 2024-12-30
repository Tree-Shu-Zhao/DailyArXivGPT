import json
import os
from datetime import datetime

import yaml
from flask import Flask
from loguru import logger

from src.workflow import Workflow
from flask import request

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


@app.route('/fetch', methods=['GET'])
def fetch():
    cfg = read_config(os.path.join("configs", "config.yaml"))

    # Get parameters from request, with default values
    relevance_threshold = int(request.args.get('relevance_threshold', cfg.get('relevance_threshold', 7)))
    llm_model = request.args.get('llm_model', cfg.get('llm_model', 'gpt-4o'))
    
    # Update config with new parameters
    cfg_copy = cfg.copy()
    cfg["reader"]["llm_model"] = llm_model
    cfg["reader"]["relevance_threshold"] = relevance_threshold

    logger.info(f"\n{json.dumps(cfg_copy, indent=4)}")
    
    workflow = Workflow(cfg_copy)
    return workflow.run()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=33678)