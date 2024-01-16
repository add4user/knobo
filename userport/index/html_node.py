from dataclasses import dataclass, field
from typing import List
from queue import Queue
import textwrap


@dataclass
class HTMLNode:
    """
    Representation of a tag or raw string within a HTML document.
    """
    # Name of tag (h, p, a, ul, li etc.) or None if it is a string node.
    tag_name: str = None
    # Applies to only string nodes.
    text: str = None
    # Applies to <a> or <img> nodes.
    url: str = None
    # Whether this node is a placeholder or not. Used by parser.
    placeholder: bool = False
    # Only applicable to tag nodes (h, p, a, ul, li etc.)
    child_nodes: List['HTMLNode'] = field(default_factory=list)

    # Delta indentation at each child.
    delta_indentation = " "

    def to_str(self, indentation: str = "") -> str:
        """
        Return string representation of the node and its children.
        """
        if self.tag_name == None:
            # We want to replace intra string new lines with spaces.
            return self.text
            # Uncomment this for debugging purposes.
            # return repr(self.text)

        # Fetch string values of children.
        child_str_list: List[str] = []
        bullet_point: str = "\u2022"
        list_number: int = 1
        for child_node in self.child_nodes:
            val = child_node.to_str(
                indentation=indentation + HTMLNode.delta_indentation)

            if child_node.tag_name == None and self.tag_name != 'pre':
                # This is a text string.
                # If not preformatted, replace newlines within the string.
                val = val.replace('\n', ' ')

            # Add bullet points to <li> elements.
            if (child_node.tag_name == 'li' and self.tag_name == 'ul') or \
                    (child_node.tag_name == 'dt' and self.tag_name == 'dl'):
                val = f'\n\n{bullet_point} {val.lstrip()}'
            elif child_node.tag_name == 'li' and self.tag_name == 'ol':
                val = f'\n\n{str(list_number)}. {val.lstrip()}'
                list_number += 1

            child_str_list.append(val)

        child_str = "".join(child_str_list)

        if self.tag_name == 'a' and self.url:
            child_str = f'{child_str} ({self.url})'
        elif self.tag_name == 'img' and self.url:
            child_str = f'\n\nReference Image: {self.url} {child_str}'
        elif self.tag_name == 'em':
            child_str = f'`{child_str}`'
        elif self.tag_name in set({'strong', 'b'}):
            child_str = f'"{child_str}"'
        elif self.tag_name == 'pre':
            child_str = f'\n\n```\n{child_str}```'
        elif self.tag_name == 'li' or self.tag_name == 'dt' or self.tag_name == 'dd':
            # Add new lines to separate from next list item.
            child_str = f'{child_str}'
        elif self.tag_name == 'ul' or self.tag_name == 'ol' or self.tag_name == 'dl':
            # return f'\n{textwrap.indent(child_str, prefix=self.indentation)}'
            child_str = f'\n{child_str}'
        elif self.tag_name == 'p':
            # The new lines help leave a blank line before the next tag's string.
            # This may end up leaving more new lines when enclosed inside an <li>
            # tag since we are adding new blank line after that tag as well.
            child_str = f'\n\n{child_str}'
        elif self.tag_name.startswith('h'):
            child_str = f'\n\n\n\n{child_str}'

        return textwrap.indent(child_str, indentation)


@dataclass
class HTMLSection:
    """
    Representation of a section on a HTML Page. A section consits of formatted text
    as well as child sections. Do not instantiate this class directly.
    """
    ROOT_TEXT = 'root'
    # Text in the section. The text includes the section title as well.
    text: str = ""
    # Child sections under this section.
    child_sections: List['HTMLSection'] = field(default_factory=list)

    def is_root_section(self):
        return self.text == HTMLSection.ROOT_TEXT


def convert_to_sections(root_node: HTMLNode, max_depth: int = 1) -> HTMLSection:
    """
    Convert given HTML Nodes sections and returns the root section. HTMLSections contain information
    that will be stored in the database as a representation of the page.

    Max depth represents the maximum depth from given root node that BFS will
    traverse to generate new sections. The default is 1 i.e. only upto
    the first level of child nodes.
    """
    assert root_node.tag_name.startswith(
        'root'), f"Invalid tag name: {root_node.tag_name}, expected 'root'"
    q = Queue()
    root_section = HTMLSection(text=HTMLSection.ROOT_TEXT)
    for cnode in root_node.child_nodes:
        q.put((cnode, root_section, 1))

    while not q.empty():
        qVal = q.get()
        node: HTMLNode = qVal[0]
        parent_section: HTMLSection = qVal[1]
        current_depth = qVal[2]

        max_depth_exceeded = True if current_depth > max_depth else False
        child_heading_nodes: List[HTMLNode] = []
        text_list: List[str] = []
        for child_node in node.child_nodes:
            if max_depth_exceeded:
                # Convert child node to string and append to list.
                text_list.append(child_node.to_str())
                continue

            # Max depth not exceeded, separate heading nodes into a new section.
            if child_node.tag_name and child_node.tag_name.startswith('h'):
                child_heading_nodes.append(child_node)
                continue

            # Convert text node to string and append to list.
            text_list.append(child_node.to_str())

        html_section = HTMLSection()
        html_section.text = "".join(text_list)
        # Append text of child to parent HTML section.
        parent_section.child_sections.append(html_section)

        if not max_depth_exceeded:
            # BFS on child nodes.
            for child_heading_node in child_heading_nodes:
                q.put((child_heading_node, html_section, current_depth+1))

            current_depth += 1

    return root_section
