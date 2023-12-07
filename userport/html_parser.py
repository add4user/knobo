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
        self.unwanted_tags = set({'script', 'style'})
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

        if tag.startswith('h') or tag in set({'p', 'ul', 'ol', 'li', 'a'}):
            new_node = Node(tag_name=tag)
            self.current_open_nodes.append(new_node)

    def handle_data(self, data):
        if not self.start_parsing or self.end_parsing or self.unwanted_tag_in_progress:
            return
        # Append data to last node's children.
        text_only_node = Node(text=data)
        if len(self.current_open_nodes) == 0:
            # Edge case, skip for now.
            # TODO: handle this.
            print("Found no nodes for: ", data)
            return
        last_node = self.current_open_nodes[-1]
        last_node.child_nodes.append(text_only_node)

    def handle_endtag(self, tag):
        if not self.start_parsing or self.end_parsing:
            return
        if tag in self.unwanted_tags:
            self.unwanted_tag_in_progress = False
            return

        if len(self.current_open_nodes) == 0:
            # Do nothing.
            return

        last_node = self.current_open_nodes[-1]
        if tag != last_node.tag_name:
            # Do nothing.
            return
        self.current_open_nodes.pop()
        if len(self.current_open_nodes) > 0:
            # Add as child to prev parent.
            self.current_open_nodes[-1].child_nodes.append(last_node)
        else:
            # Find parent from heading nodes and link them.
            parent_heading_node = self.get_parent_heading_node(tag)
            if not parent_heading_node:
                parent_heading_node = self.root_node

            parent_heading_node.child_nodes.append(last_node)

            if tag.startswith("h"):
                self.active_heading_nodes.append(last_node)

    def get_parent_heading_node(self, current_tag: str) -> Optional[Node]:
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
            if footer_keyword in set(values.split()):
                return True

        return False


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
    print(indent, node.tag_name)
    indent += "  "
    for child_node in node.child_nodes:
        if child_node.tag_name == None:
            print(indent, child_node.text)
        else:
            print_node_heirarchy(child_node, indent)


def fetch_html_page(url: str) -> str:
    response = requests.get(url)
    content_type: str = response.headers['content-type']
    if "text/html" not in content_type:
        raise ValueError(
            f'Invalid Content Type; expected text/html, got {content_type}')
    return response.text


def save_to_file(html_page: str):
    with open('test_html.txt', 'w') as f:
        f.write(html_page)


# url = 'https://requests.readthedocs.io/en/latest/user/quickstart/'
url = 'https://www.mongodb.com/docs/compass/current/indexes/create-search-index/'
html_page = fetch_html_page(url)
parse_html(html_page)
save_to_file(html_page)
