import hydra
from loguru import logger
from flask import Flask
from omegaconf import OmegaConf

from src.workflow import Workflow

logger.add("logs/{time}.log", rotation="12:00")

app = Flask(__name__)

@hydra.main(config_path="configs", config_name="config", version_base=None)
@app.route('/fetch', methods=['GET'])
def main(cfg):
    logger.info(f"\n{OmegaConf.to_yaml(cfg)}")
    workflow = Workflow(cfg)
    workflow.run()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)