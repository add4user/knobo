from dataclasses import dataclass, field
from typing import List
import textwrap


@dataclass
class Node:
    # Name of tag (h, p, a, ul, li etc.) or None if it is a string node.
    tag_name: str = None
    # Applies to only string nodes.
    text: str = None
    # Applies to a ang img nodes.
    url: str = None
    # Identation applied to ul or ol nodes.
    indentation: str = ""
    # Only applicable to tag nodes (h, p, a, ul, li etc.)
    child_nodes: List['Node'] = field(default_factory=list)

    def to_str(self) -> str:
        """
        Return string representation of the node.
        """
        if self.tag_name == None:
            return self.text

        # Fetch string values of children.
        child_str_list: List[str] = []
        bullet_point: str = "\u2022"
        for child_node in self.child_nodes:
            val = child_node.to_str()
            if child_node.tag_name == 'li':
                if self.tag_name == 'ul' or self.tag_name == 'ol':
                    # TODO: Add numbers for ol.
                    # prepend_text: str = bullet_point if tag.name == "ul" else f"{str(list_count)}."
                    val = f'{bullet_point} {val}'

            if self.tag_name.startswith('h') and child_node.tag_name == None:
                # Add new line for the title.
                val = f'{val}\n\n'

            child_str_list.append(val)

        if self.tag_name == 'p':
            child_str_list.append("\n\n")
            # if self.child_nodes[0].text == 'On this page':
            #     print("BROOO")
            #     print(child_str_list)

        child_str = "".join(child_str_list)

        if self.tag_name == 'a' and self.url:
            return f'{child_str} ({self.url})'
        elif self.tag_name == 'img' and self.url:
            return f'Reference Image: {self.url} {child_str}'
        elif self.tag_name == 'em':
            return f'`{child_str}`'
        elif self.tag_name == 'b' or self.tag_name == 'strong':
            return f'"{child_str}"'
        elif self.tag_name == 'li':
            # Add new lines to separate from next list item.
            return f'{child_str}\n\n'
        elif self.tag_name == 'ul' or self.tag_name == 'ol':
            return f'{textwrap.indent(child_str, prefix=self.indentation)}\n\n'

        return child_str
