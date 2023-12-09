from dataclasses import dataclass, field
from typing import List
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
    # Applies to a ang img nodes.
    url: str = None
    # Whether this node is a placeholder or not. Used by parser.
    placeholder: bool = False
    # Only applicable to tag nodes (h, p, a, ul, li etc.)
    child_nodes: List['HTMLNode'] = field(default_factory=list)

    # Delta indentation at each child.
    delta_indentation = " "

    def to_str(self, indentation: str = "") -> str:
        """
        Return string representation of the node and its childresn.
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
            child_str = f'Reference Image: {self.url} {child_str}'
        elif self.tag_name == 'em':
            child_str = f'`{child_str}`'
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
            if self.tag_name == 'h2':
                # TODO: This tag_name should be dynamic i.e.
                # whatever is the second highest heading in the
                # specific HTML file.
                child_str = f'\n\n\n\n{child_str}'
            else:
                child_str = f'\n\n{child_str}'

        return textwrap.indent(child_str, indentation)
