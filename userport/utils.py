"""
Helper methods for the application.
"""
import requests
import hashlib
import re
from datetime import datetime
from typing import List
from urllib.parse import urljoin, urlparse
from slack_sdk import WebClient
import os
from flask import g

# TODO: Change to custom domain in production and make sure it's not hardcoded.
_HARDCODED_HOSTNAME_URL = 'https://fb5e-2409-40f2-1041-7619-857c-13e-96b0-e84d.ngrok-free.app'


def get_slack_web_client() -> WebClient:
    """
    Helper to get slack web client. Works only in
    Flask request context.
    """
    if 'slack_web_client' not in g:
        # Create a new client and connect to the server
        g.slack_web_client = WebClient(
            token=os.environ['SLACK_OAUTH_BOT_TOKEN'])

    return g.slack_web_client


def get_hostname_url() -> str:
    """
    Helper to return Hostname URL.
    """
    return _HARDCODED_HOSTNAME_URL


def get_domain_from_email(email: str):
    """
    Parse domain from given string.
    Raises error if string doesn't contain @ string.
    """
    if '@' not in email:
        raise ValueError(f'Invalid email string: f{email}')
    _, domain = email.split('@')
    return domain


def fetch_html_page(url: str) -> str:
    """
    Fetch HTML page for gien URL.
    """
    response = requests.get(url)
    content_type: str = response.headers['content-type']
    if "text/html" not in content_type:
        raise ValueError(
            f'Invalid Content Type; expected text/html, got {content_type}')
    return response.text


def generate_hash(key: str) -> str:
    """
    Helper to hash an existing key. Returns hex string of length 16.
    """
    h = hashlib.shake_256(key.encode('utf-8'))
    return h.hexdigest(16)


def convert_to_markdown_heading(text: str, level: int):
    """
    Convert text to Markdown heading with given level.
    Number should be >= 1.
    """
    assert level >= 1, f"Expected heading level >=1, got {level}"
    prefix = "#" * level
    return f"{prefix} {text}"


def get_heading_level_and_content(markdown_text: str) -> (int, str):
    """
    Return Heading level and content from given markdown text. Throws
    error if text is input is not a markdown formatted heading.
    """
    match = _get_heading_markdown_match(markdown_text)
    return len(match.group(1)), match.group(2)


def get_heading_level(markdown_text: str) -> int:
    """
    Return Heading level from given markdown text. Throws
    error if text is input is not a markdown formatted heading.
    """
    match = _get_heading_markdown_match(markdown_text)
    return len(match.group(1))


def get_heading_content(markdown_text: str) -> (int, str):
    """
    Return Heading content from given markdown text. Throws
    error if text is input is not a markdown formatted heading.
    """
    match = _get_heading_markdown_match(markdown_text)
    return match.group(2)


def _get_heading_markdown_match(markdown_text: str) -> re.Match:
    """
    Helper that returns match for heading in markdown text. Throws
    error if text is input is not a markdown formatted heading.
    """
    match = re.match(pattern=r'^(#+)\s+(.+)', string=markdown_text)
    if match:
        return match
    raise ValueError(
        f'Expected Markdown heading in text, got {repr(markdown_text)}')


def to_urlsafe_path(text: str) -> str:
    """
    Converts input text into a string that can be used in URL path.
    We only keep alphanumeric characters (in lowercase form) and converts spaces to hypens.
    We also want to stop parsing if we hit encounter an opening bracket (likely indicating a URL)
    until we encounter the corresponding closing bracket.
    """
    new_text_list: List[str] = []
    inside_open_bracket: bool = False
    for splitstr in text.split(" "):
        new_split_str_list: List[str] = []
        for c in splitstr:
            if c == "(":
                inside_open_bracket = True
            elif c == ")":
                inside_open_bracket = False
            if inside_open_bracket:
                # Stop parsing characters while inside brackets.
                continue
            if c.isalnum():
                new_split_str_list.append(c.lower())
        new_text_list.append("".join(new_split_str_list))
    return "-".join(new_text_list)


def create_documentation_url(host_name: str, team_domain: str, page_html_id: str, section_html_id: str) -> str:
    """
    Create URL from given host name and page and section.
    """
    return urljoin(host_name, f"{team_domain}/{page_html_id}#{section_html_id}")


def get_endpoint(url: str):
    """
    Removes the hostname from a URL and returns the endpoint string.

    Raises exception if the URL is invalid.
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme and parsed_url.path:
        if parsed_url.fragment:
            return f'{parsed_url.path}#{parsed_url.fragment}'
        return parsed_url.path

    raise ValueError(f'Could not fetch hostname, invalid format of URL: {url}')


def to_day_format(datetime_obj: datetime) -> str:
    """
    Return datetime object formatted to YYYY-MM-DD.
    """
    return datetime_obj.strftime('%b %d, %Y')
