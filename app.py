import json
import os
from datetime import datetime

import yaml
from flask import Flask, Response
from loguru import logger
from feedgen.feed import FeedGenerator

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

def create_rss_feed(papers):
    # Create an RSS feed
    fg = FeedGenerator()
    
    # Set feed metadata
    fg.title('Relevant Research Papers Feed')
    fg.description('Latest research papers relevant to my interests')
    fg.link(href='http://192.168.0.126:33678/rss')
    fg.language('en')
    
    try:
        # Add each paper as a feed entry
        for paper in papers:
            fe = fg.add_entry()
            fe.title(paper['title'])
            fe.description(f"Relevance Score: {paper['relevance_score']}\nReasons: {paper['relevance_reasons']}\n\n{paper['abstract']}")
            
            # If no publication date is available, use current time
            fe.published(datetime.now())
            
            # Generate unique ID for each entry (you might want to adjust this)
            fe.id(str(hash(paper['title'])))
    
    except Exception as e:
        # Handle errors gracefully
        fg.description(f'Error fetching papers: {str(e)}')
    
    # Generate the RSS feed
    rssfeed = fg.rss_str(pretty=True)

    return rssfeed


@app.route('/rss', methods=['GET'])
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
    
    # Run the workflow to process papers
    workflow = Workflow(cfg_copy)
    papers =  workflow.run()

    # Create an RSS feed
    rss_feed = create_rss_feed(papers)
    return Response(rss_feed, mimetype='application/rss+xml')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=33678)