from html.parser import HTMLParser
from bs4 import BeautifulSoup
from text_node import Node
from typing import List, Optional
import requests


class CustomHTMLParser(HTMLParser):
    """
    Parses HTML page and stores them as heirarchical text sections.
    """

    def __init__(self, *, convert_charrefs: bool = True) -> None:
        super().__init__(convert_charrefs=convert_charrefs)
        self.first_tag_to_start_parsing: str = None
        self.start_parsing = False
        self.end_parsing = False
        # Tracks list of active heading nodes in the document.
        self.active_heading_nodes: List[Node] = []
        # Root Text Node.
        self.root_node: Node = Node(tag_name='root')
        # Unwanted tags that we don't want to parse data of.
        self.unwanted_tags = set({'script', 'style', 'hr'})
        self.unwanted_tag_in_progress = False
        # Current nodes in progress. Popped after end tag.
        self.current_open_nodes: List[Node] = []

    def find_starting_heading_tag(self, html_page: str):
        """
        Finds first of h1,h2, h3 or h4 tags. If none found, throws an error.
        """
        soup = BeautifulSoup(html_page, 'html.parser')
        if soup.find('h1'):
            self.first_tag_to_start_parsing = 'h1'
        elif soup.find('h2'):
            self.first_tag_to_start_parsing = 'h2'
        elif soup.find('h3'):
            self.first_tag_to_start_parsing = 'h3'
        elif soup.find('h4'):
            self.first_tag_to_start_parsing = 'h4'
        else:
            raise ValueError('Error! No heading tags found in document')

    """
    Methods below are executed after 'feed' method is called.
    """

    def handle_starttag(self, tag, attrs):
        """
        Callback for when a new tag is encountered.
        """
        if self.end_parsing:
            return

        # Check condition to start parsing (if not parsing already).
        if not self.start_parsing:
            if tag == self.first_tag_to_start_parsing:
                self.start_parsing = True
            else:
                return

        if CustomHTMLParser.is_end_of_content(tag=tag, attrs=attrs):
            self.end_parsing = True
            return

        if tag in self.unwanted_tags:
            self.unwanted_tag_in_progress = True
            return

        if tag.startswith('h') or tag in set({'p', 'ul', 'ol', 'li', 'a', 'em', 'pre', 'dl', 'dt', 'dd'}):
            new_node = Node(tag_name=tag)

            # Add <a> tag URL to the node if it exists.
            if tag == 'a':
                new_node = CustomHTMLParser._add_url_to_node(
                    node=new_node, attrs=attrs)

            self.current_open_nodes.append(new_node)

    def handle_data(self, data):
        """
        Callback when new data is received.
        """
        if not self.start_parsing or self.end_parsing or self.unwanted_tag_in_progress:
            return

        if len(self.current_open_nodes) == 0:
            if data.strip() == "":
                # Unncessary newlines or whitespaces. Skip storing in placeholder.
                return

            # Might be text directly inside a <div>.
            # We should create a placeholder <p> node to handle this.
            placeholder_node = Node(tag_name='p', placeholder=True)
            self.current_open_nodes.append(placeholder_node)

        # Append data to last current ndoe.
        last_node = self.current_open_nodes[-1]
        if len(last_node.child_nodes) > 0 and last_node.child_nodes[-1].tag_name == None:
            # If last child node is a pure string, just append to it instead of creating a new node.
            last_node.child_nodes[-1].text += data
        else:
            # Create new text node and append to last node's children.
            text_only_node = Node(text=data)
            last_node.child_nodes.append(text_only_node)

    def handle_endtag(self, tag):
        """
        Callback when an endtag is encountered.
        """
        if not self.start_parsing or self.end_parsing:
            return
        if tag in self.unwanted_tags:
            self.unwanted_tag_in_progress = False
            return

        if len(self.current_open_nodes) == 0:
            # Do nothing.
            return

        last_node = self.current_open_nodes[-1]
        if not last_node.placeholder and tag != last_node.tag_name:
            # Do nothing since this tag doesn't match last node's tag.
            # When last node is a placeholder, we don't expect a match
            # since the node was created by us.
            return

        self.current_open_nodes.pop()
        if len(self.current_open_nodes) > 0:
            # Add as child to prev open node.
            self.current_open_nodes[-1].child_nodes.append(last_node)
        else:
            # Find parent from active heading nodes and link them.
            parent_heading_node = self._get_parent_heading_node(tag)
            if not parent_heading_node:
                parent_heading_node = self.root_node

            parent_heading_node.child_nodes.append(last_node)

            if tag.startswith("h"):
                # Only heading nodes can be parent nodes.
                self.active_heading_nodes.append(last_node)

    def _get_parent_heading_node(self, current_tag: str) -> Optional[Node]:
        """
        Returns parent heading node of given heading tag
        """

        if len(self.active_heading_nodes) == 0:
            return None

        while len(self.active_heading_nodes) > 0:
            if not current_tag.startswith('h'):
                return self.active_heading_nodes[-1]

            parent_tag_name = self.active_heading_nodes[-1].tag_name
            if parent_tag_name.startswith("h") and int(parent_tag_name[1:]) < int(current_tag[1:]):
                # Found parent section.
                return self.active_heading_nodes[-1]
            else:
                # Remove this heading since current heading is larger (in format).
                self.active_heading_nodes.pop()

        raise ValueError(
            f'Error! Could not find parent heading section for {current_tag}')

    @staticmethod
    def is_end_of_content(tag, attrs) -> bool:
        """
        footer in tag or attrs signals end of parsing main content.
        TODO: Come up with better algorithm in the future.
        """
        footer_keyword = 'footer'
        if tag == footer_keyword:
            return True
        for attr in attrs:
            _, values = attr
            if not values:
                continue
            if footer_keyword in set(values.split()):
                return True

        return False

    @staticmethod
    def _add_url_to_node(node: Node, attrs) -> Node:
        for attr in attrs:
            if 'href' in attr[0]:
                node.url = attr[1]
        return node


def parse_html(html_page: str):
    parser = CustomHTMLParser()
    parser.find_starting_heading_tag(html_page)
    parser.feed(html_page)

    print(parser.root_node.to_str())
    # print_node_heirarchy(parser.root_node)


def print_node_heirarchy(node: Node, indent=""):
    """
    Prints list of nodes and child nodes with indentation
    so the parsing algorithm can be debugged.
    """
    print(indent, node.tag_name, " placeholder: ", node.placeholder)
    indent += "  "
    for child_node in node.child_nodes:
        if child_node.tag_name == None:
            print(indent, repr(child_node.text))
        else:
            print_node_heirarchy(child_node, indent)


def fetch_html_page(url: str) -> str:
    response = requests.get(url)
    content_type: str = response.headers['content-type']
    if "text/html" not in content_type:
        raise ValueError(
            f'Invalid Content Type; expected text/html, got {content_type}')
    return response.text


# url = 'https://requests.readthedocs.io/en/latest/user/quickstart/'
# url = 'https://flask.palletsprojects.com/en/3.0.x/tutorial/layout/'
# url = 'https://flask.palletsprojects.com/en/3.0.x/tutorial/factory/'
# url = 'https://docs.python.org/3/library/html.parser.html'
# url = 'https://www.mongodb.com/docs/atlas/tutorial/test-resilience/test-primary-failover/'
url = 'https://www.mongodb.com/docs/compass/current/indexes/create-search-index/'
html_page = fetch_html_page(url)
parse_html(html_page)
