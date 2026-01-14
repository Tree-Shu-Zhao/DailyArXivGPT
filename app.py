import json
import os
from datetime import datetime

import pytz
import yaml
from feedgen.feed import FeedGenerator
from flask import Flask, Response, request, send_file, jsonify
from loguru import logger

from src.workflow import Workflow
from src.podcast_workflow import PodcastWorkflow

# Set timezone
tz_info = pytz.timezone(os.environ.get("TZ", "America/New_York"))

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
        current_time = datetime.now(tz_info)
        for i, paper in enumerate(papers):
            fe = fg.add_entry()
            fe.title(paper['title'])
            fe.title(f"[{paper['relevance_score']}]{paper['title']}")
            fe.description(f"""{paper['abstract']}

===SUMMARY===
{paper['key_contributions']}""")
            
            # If no publication date is available, use current time
            entry_time = current_time.timestamp() + i
            fe.published(datetime.fromtimestamp(entry_time, tz_info))

            # Generate unique ID for each entry (you might want to adjust this)
            fe.id(paper['link'])
    
    except Exception as e:
        # Handle errors gracefully
        fg.description(f'Error fetching papers: {str(e)}')
    
    # Generate the RSS feed
    rssfeed = fg.rss_str(pretty=True)

    return rssfeed


@app.route('/rss', methods=['GET'])
def fetch():
    cfg = read_config(os.path.join("configs", "config.yaml"))

    logger.info(f"\n{json.dumps(cfg, indent=4)}")

    # Run the workflow to process papers
    workflow = Workflow(cfg)
    papers =  workflow.run()

    # Create an RSS feed
    rss_feed = create_rss_feed(papers)
    return Response(rss_feed, mimetype='application/rss+xml')


@app.route('/podcast', methods=['GET'])
def podcast():
    """Generate or serve today's podcast.

    Query params:
        date: Optional date (YYYY-MM-DD), defaults to today
        format: 'audio' (default) or 'json' (script only)

    Returns:
        - If format=audio and audio exists: Audio file (audio/mpeg)
        - If format=json: JSON with script and metadata
        - If TTS not configured: JSON with script and error message
    """
    cfg = read_config(os.path.join("configs", "config.yaml"))

    date_param = request.args.get('date')
    output_format = request.args.get('format', 'audio')

    try:
        workflow = PodcastWorkflow(cfg)
        result = workflow.run(date_param)

        if output_format == 'json':
            return jsonify(result)

        # Return audio if available
        if result.get('audio_path') and os.path.exists(result['audio_path']):
            return send_file(
                result['audio_path'],
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=f"podcast-{result['date']}.mp3"
            )

        # No audio - return JSON with explanation
        return jsonify({
            **result,
            "message": "Audio not generated - TTS credentials not configured"
        }), 200  # Still 200 since script was generated

    except ValueError as e:
        logger.error(f"Podcast generation failed: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Podcast generation failed: {e}")
        return jsonify({"error": "Podcast generation failed"}), 500


if __name__ == "__main__":
    log_file = f"logs/{datetime.now().strftime('%Y-%m-%d')}.log"
    logger.add(log_file, rotation="1 day", mode="a")

    app.run(host="0.0.0.0", port=33678)