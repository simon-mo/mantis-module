import os
import json

import requests
from structlog import get_logger

logger = get_logger()


def parse_custom_args(custom_args):
    if not custom_args:
        return dict()

    init_args = dict()
    for k, v in map(lambda s: s.split("="), custom_args.split(",")):
        init_args[k] = v
    logger.msg(f"Custom arguments are not None. The parsed result is {init_args}")
    return init_args


def post_result_to_slack(markdown_result, text_to_image_links={}):
    url = os.environ["SLACK_ENDPOINT"]

    payload = {
        "username": "Fissure Bot",
        "icon_emoji": ":tiger:",
        "channel": "#mantis-experiments",  # Comment this to default to Simon's DM
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": markdown_result}},
        ]
        + [
            {
                "type": "image",
                "title": {"type": "plain_text", "text": text},
                "image_url": image,
                "alt_text": "result plot",
            }
            for text, image in text_to_image_links.items()
        ],
    }

    resp = requests.post(url, json=payload)
    print(f"Post result {resp}")
    if resp.status_code != 200:
        print(f"Post result errroed: {resp.text}")
        print(f"Payload was: {json.dumps(payload)}")
