import re
import copy
import pprint
from typing import List, Union, Optional, Dict
from userport.slack_blocks import (
    RichTextBlock,
    RichTextSectionElement,
    RichTextListElement,
    RichTextPreformattedElement,
    RichTextQuoteElement,
    RichTextObject,
    RichTextStyle
)


class MarkdownToRichTextConverter:
    """
    Converts Markdown formatted text to Slack Rich Text Blocks.

    Slack recommends Rich Text block based formatted over using in-house 'markdwn'
    for formatting text.

    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text.
    """

    def __init__(self) -> None:
        self._init_values()

    def _init_values(self):
        # List of completed elements are stored in this list and later used to construct the final RichTextBlock.
        self.completed_elements: List[Union[RichTextSectionElement, RichTextListElement,
                                            RichTextPreformattedElement, RichTextQuoteElement]] = []

        # This stores the current rich text element to which we will add text object elements or section elements (if list).
        self.current_element: Optional[Union[RichTextSectionElement, RichTextListElement,
                                             RichTextPreformattedElement, RichTextQuoteElement]] = None

    def get_html(self, markdown_text: str) -> str:
        """
        Convert given Markdown text into HTML.
        """
        self._init_values()
        return self.convert(markdown_text=markdown_text).get_html()

    def convert(self, markdown_text: str) -> RichTextBlock:
        """
        Convert given Markdown text into a RichTextBlock element and return it.
        """
        self._init_values()
        markdown_lines = markdown_text.split("\n")
        for text in markdown_lines:
            if len(text) == 0:
                # Since we have split by newlines, we add that back.
                text = "\n"
            if self._check_if_preformatted_elem(text):
                continue
            elif self._check_if_within_preformatted_block(text):
                continue
            elif self._check_if_block_quote_elem(text):
                continue
            elif self._check_if_bullet_list_elem(text):
                continue
            elif self._check_if_ordered_list_elem(text):
                continue
            else:
                self._process_as_section_elem(text)

        if self.current_element:
            # Add current element to completed list.
            self.completed_elements.append(self.current_element)

        return RichTextBlock(elements=self.completed_elements)

    def _check_if_preformatted_elem(self, text: str) -> bool:
        """
        Checks if text is a preformatted element and if so creates or closes a
        RichTextPreformattedElement. Returns False otherwise.
        """
        pattern = r'```'
        match = re.match(pattern=pattern, string=text)
        if not match:
            return False

        if self.current_element:
            # Add current element to completed list.
            self._add_trailing_newline_to_section_element_if_necessary()
            self.completed_elements.append(self.current_element)

        if isinstance(self.current_element, RichTextPreformattedElement):
            # Close the existing element.
            self.current_element = None
        else:
            # Create a new preformatted element and assign it to the current element.
            self.current_element = RichTextPreformattedElement(
                elements=[], border=0)

        return True

    def _check_if_within_preformatted_block(self, text: str) -> bool:
        """
        Checks if text is part of a preformatted text block and if so, adds to
        the existing RichTextPreformattedElement. Returns False otherwise.
        """
        if not isinstance(self.current_element, RichTextPreformattedElement):
            return False

        # Slack does not allow inline formatting inside preformatted code blocks.
        # We can just append to the previous element if it exists or create a new one
        # if it doesn't exist.
        text_objects: List[RichTextObject] = self._create_text_objects(text)
        combined_text = "".join([text_obj.text for text_obj in text_objects])

        current_element: RichTextPreformattedElement = self.current_element
        if len(current_element.elements) == 0:
            # Create a new element and append to elements.
            current_element.elements.append(RichTextObject(
                type=RichTextObject.TYPE_TEXT, text=combined_text))
        else:
            if not current_element.elements[-1].text.endswith("\n"):
                # We need to prepend newline because each text within preformaated block is separated by newline
                # so that the Slack Rich Text formatting is accurate. This should only be done
                # if the previous character is not a newline character already.
                combined_text = "\n" + combined_text
            current_element.elements[-1].text = current_element.elements[-1].text + combined_text

        return True

    def _check_if_block_quote_elem(self, text: str) -> bool:
        """
        Checks if text is a block quote element and if so it processes text
        into RichTextQuoteElement. Returns False otherwise.
        """
        # We want to also capture all whitespaces after the first one following > as part of the content.
        # To skip these whitespaces, use r'^>\s+(.*)$' instead.
        pattern = r'^>\s(.*)$'
        match = re.match(pattern=pattern, string=text)
        if not match:
            return False

        quote_content: str = match.group(1)
        if len(quote_content) == 0:
            # Empty content means its a newline since split text by newlines at the top.
            quote_content = "\n"

        text_objects: List[RichTextObject] = self._create_text_objects(
            quote_content)
        if self.current_element and \
                isinstance(self.current_element, RichTextQuoteElement):
            # Current element is part of the same block, add to it.
            current_element: RichTextQuoteElement = self.current_element
            assert len(
                current_element.elements) > 0, f"Expected at least 1 element in RichTextQuoteElement, got {current_element}"
            last_elem: RichTextObject = current_element.elements[-1]

            if not last_elem.text.endswith("\n"):
                # We need to add a new line if the last elem text did not end with newline.
                # This is because we separated text by newlines initially during parsing.
                if last_elem.is_plain_text():
                    last_elem.text = last_elem.text + "\n"
                else:
                    text_obj = RichTextObject(
                        type=RichTextObject.TYPE_TEXT, text="\n")
                    current_element.elements.append(text_obj)
                    last_elem = text_obj

            for text_obj in text_objects:
                if text_obj.is_plain_text() and last_elem.is_plain_text():
                    # Merge the text into the last plain text element.
                    last_elem.text = last_elem.text + text_obj.text
                else:
                    # Add text object to list.
                    current_element.elements.append(text_obj)
                    last_elem = text_obj
        else:
            # Create a new block quote element.
            if self.current_element:
                self._add_trailing_newline_to_section_element_if_necessary()
                self.completed_elements.append(self.current_element)
            self.current_element = RichTextQuoteElement(elements=text_objects)

        return True

    def _check_if_ordered_list_elem(self, text: str) -> bool:
        """
        Checks if text is ordered list element and if so it processes text
        into RichTextListElement. Returns False otherwise.
        """
        # We want to also capture all whitespaces after the first one following "number" as part of the content.
        # To skip these whitespaces, use r'^(\s*)(?<!\\)(\d+)\.\s+(.*)$' instead.
        pattern = r'^(\s*)(?<!\\)(\d+)\.\s(.*)$'
        match = re.match(pattern=pattern, string=text)
        if not match:
            return False

        num_leading_spaces = len(match.group(1))
        list_number = int(match.group(2))
        list_content: str = match.group(3)

        assert num_leading_spaces % 4 == 0, f"Invalid number of spaces in indentation {repr(match.group(1))}"
        assert list_number >= 1, f"Invalid list number {list_number}"

        indent = int(num_leading_spaces/4)
        section_element: RichTextSectionElement = RichTextSectionElement(
            elements=self._create_text_objects(list_content))
        if self.current_element and \
                isinstance(self.current_element, RichTextListElement) and \
                self.current_element.style == RichTextListElement.STYLE_ORDERED and \
                self.current_element.indent == indent:
            # Current element is part of the same list, just add to it.
            current_element: RichTextListElement = self.current_element
            current_element.elements.append(section_element)
        else:
            # Create a new ordered list.
            if self.current_element:
                self._add_trailing_newline_to_section_element_if_necessary()
                self.completed_elements.append(self.current_element)

            offset = list_number-1
            self.current_element = RichTextListElement(
                style=RichTextListElement.STYLE_ORDERED,
                indent=indent,
                offset=offset,
                elements=[]
            )
            self.current_element.elements.append(section_element)

        return True

    def _check_if_bullet_list_elem(self, text: str) -> bool:
        """
        Checks if text is bullet list element and if so it processes text
        into RichTextListElement. Returns False otherwise.
        """
        # We want to also capture all whitespaces after the first one following * as part of the content.
        # To skip these whitespaces, use '^(\s*)([*])\s+(.*)$' instead.
        pattern = '^(\s*)([*])\s(.*)$'
        match = re.match(pattern=pattern, string=text)
        if not match:
            return False

        num_leading_spaces = len(match.group(1))
        list_content: str = match.group(3)

        assert num_leading_spaces % 4 == 0, f"Invalid number of spaces in indentation {repr(match.group(1))}"
        indent = int(num_leading_spaces/4)
        section_element: RichTextSectionElement = RichTextSectionElement(
            elements=self._create_text_objects(list_content))
        if self.current_element and \
                isinstance(self.current_element, RichTextListElement) and \
                self.current_element.style == RichTextListElement.STYLE_BULLET and \
                self.current_element.indent == indent:
            # Current element is part of the same list, just add to it.
            current_element: RichTextListElement = self.current_element
            current_element.elements.append(section_element)
        else:
            # Create a new bullet list.
            if self.current_element:
                self._add_trailing_newline_to_section_element_if_necessary()
                self.completed_elements.append(self.current_element)

            self.current_element = RichTextListElement(
                style=RichTextListElement.STYLE_BULLET,
                indent=indent,
                elements=[]
            )
            self.current_element.elements.append(section_element)

        return True

    def _process_as_section_elem(self, text: str):
        """
        Process text as RichTextSectionElement.
        """
        text_objects: List[RichTextObject] = self._create_text_objects(text)
        if isinstance(self.current_element, RichTextSectionElement):
            # Add to existing element.
            current_element: RichTextSectionElement = self.current_element
            assert len(
                current_element.elements) > 0, f"Expected at least 1 element in RichTextSectionElement, got {current_element}"
            last_elem: RichTextObject = current_element.elements[-1]

            if not last_elem.text.endswith("\n"):
                # We need to add a new line if the last elem text did not end with newline.
                # This is because we separated text by newlines initially during parsing.
                if last_elem.is_plain_text():
                    last_elem.text = last_elem.text + "\n"
                else:
                    text_obj = RichTextObject(
                        type=RichTextObject.TYPE_TEXT, text="\n")
                    current_element.elements.append(text_obj)
                    last_elem = text_obj

            for text_obj in text_objects:
                if text_obj.is_plain_text() and last_elem.is_plain_text():
                    # Merge the text into the last plain text element.
                    last_elem.text = last_elem.text + text_obj.text
                else:
                    # Add text object to list.
                    current_element.elements.append(text_obj)
                    last_elem = text_obj
        else:
            # Create a new element.
            if self.current_element:
                self.completed_elements.append(self.current_element)
            self.current_element = RichTextSectionElement(
                elements=text_objects)

    def _add_trailing_newline_to_section_element_if_necessary(self):
        """
        Add a trailing newline at the end of section element if there isn't
        a newline already. This is so that when a new element like list, quote
        or preformatted is being created, we need to ensure there is a newline
        separation to the previous section element. It is kind of like the inverse operation
        in RichTextBlock.get_markdown() that we add trailing newlines for all elements
        other than section element.
        """
        if not isinstance(self.current_element, RichTextSectionElement):
            return

        current_element: RichTextSectionElement = self.current_element
        assert len(
            current_element.elements) > 0, f"Expected at least 1 element in rich text section {current_element}"

        last_elem: RichTextObject = current_element.elements[-1]
        if last_elem.text.endswith("\n"):
            # Newline already exists, no need to add.
            return
        if last_elem.is_plain_text():
            last_elem.text += "\n"
        else:
            current_element.elements.append(RichTextObject(
                type=RichTextObject.TYPE_TEXT, text="\n"))

    def _create_text_objects(self, text: str) -> List[RichTextObject]:
        """
        Returns a text object for every plain and styled substring of given text.
        The returned list of text objects are in order of text traversal.

        Assumes that input text is content within a Markdown block element. This makes
        the input text a Markdown inline element.
        """
        styled_index_intervals: List[List[str]] = []

        bold_matches = re.finditer(
            pattern=r'(?<!\\)\*\*(.+?)\*\*(?!\*)', string=text)
        for match in bold_matches:
            styled_index_intervals.append([match.start(), match.end()])

        italic_matches = re.finditer(
            pattern=r'(?<!\*)\*([^*_]+?)\*(?!\*)', string=text)
        for match in italic_matches:
            styled_index_intervals.append([match.start(), match.end()])

        code_matches = re.finditer(pattern=r'`(.+?)`', string=text)
        for match in code_matches:
            styled_index_intervals.append([match.start(), match.end()])

        strikethrough_matches = re.finditer(
            pattern=r'~~(.+?)~~', string=text)
        for match in strikethrough_matches:
            styled_index_intervals.append([match.start(), match.end()])

        link_matches = re.finditer(
            pattern=r'\[([^\]]+)\]\(([^)]+)\)', string=text)
        for match in link_matches:
            styled_index_intervals.append([match.start(), match.end()])

        non_overlapping_styled_intervals = self._get_non_overlapping_intervals(
            styled_index_intervals)

        all_text_objects: List[RichTextObject] = []
        prev_end_pos = 0
        for interval in non_overlapping_styled_intervals:
            start_pos, end_pos = interval
            plain_text = text[prev_end_pos:start_pos]
            if len(plain_text) > 0:
                # Create and append plain text object.
                plain_text_object = RichTextObject(
                    type=RichTextObject.TYPE_TEXT, text=plain_text)
                all_text_objects.append(plain_text_object)

            # Create and append styled object.
            styled_text: str = text[start_pos: end_pos]
            styled_text_object = self._create_styled_text_object(
                styled_text=styled_text, text_object=None, root_node=True)
            all_text_objects.append(styled_text_object)

            prev_end_pos = end_pos

        # Add final plain text if any.
        plain_text = text[prev_end_pos:]
        if len(plain_text) > 0:
            all_text_objects.append(RichTextObject(
                type=RichTextObject.TYPE_TEXT, text=plain_text))

        return all_text_objects

    def _get_non_overlapping_intervals(self, index_intervals: List[List[int]]) -> List[List[int]]:
        """
        Combine given list of index intervals into non overlapping intervals.
        This will ensure we don't have to parse the same markdown text through different
        pattern matches and manage their merge. Simplifies logic a lot.
        """
        if len(index_intervals) <= 1:
            return index_intervals
        sorted_index_intervals = sorted(index_intervals, key=lambda x: x[0])
        merged_index_intervals: List[List[str]] = [sorted_index_intervals[0]]
        for i in range(1, len(sorted_index_intervals)):
            interval = merged_index_intervals[-1]

            next_interval = sorted_index_intervals[i]
            if interval[1] <= next_interval[0]:
                # No overlap.
                merged_index_intervals.append(next_interval)
                continue

            # Merge the two.
            interval[1] = max(interval[1], next_interval[1])

        return merged_index_intervals

    def _create_styled_text_object(self, styled_text: str, text_object: Optional[RichTextObject] = None, root_node: bool = False) -> RichTextObject:
        """
        Create and return styled text object from given styled text.
        Warning: We don't throw an error if the input is not exactly formatted in one of inline styles.
        """
        if not text_object:
            # Create a default object.
            text_object = RichTextObject(
                type=RichTextObject.TYPE_TEXT, text="")

        bold_match = re.match(
            pattern=r"\*\*(.+)\*\*", string=styled_text)
        if bold_match:
            bolded_text: str = bold_match.group(1)
            if not text_object.style:
                text_object.style = RichTextStyle()
            text_object.style.bold = True
            return self._create_styled_text_object(styled_text=bolded_text, text_object=text_object)

        italic_match = re.match(
            pattern=r"\*(.+)\*", string=styled_text)
        if italic_match:
            italic_text: str = italic_match.group(1)
            if not text_object.style:
                text_object.style = RichTextStyle()
            text_object.style.italic = True
            return self._create_styled_text_object(styled_text=italic_text, text_object=text_object)

        code_match = re.match(
            pattern=r"`(.+)`", string=styled_text)
        if code_match:
            # Unlike other styles, we treat any markdown inside code blocks as plain text itself.
            text_object.text = code_match.group(1)
            if not text_object.style:
                text_object.style = RichTextStyle()
            text_object.style.code = True
            return text_object

        strikethrough_match = re.match(
            pattern=r"~~(.+)~~", string=styled_text)
        if strikethrough_match:
            strikethrough_text: str = strikethrough_match.group(1)
            if not text_object.style:
                text_object.style = RichTextStyle()
            text_object.style.strike = True
            return self._create_styled_text_object(styled_text=strikethrough_text, text_object=text_object)

        link_match = re.match(
            pattern=r'^(?P<link_text>\[([^\]]+?)\])\((?P<link_url>[^)\s]+)\)$', string=styled_text)
        if link_match:
            link_text = link_match.group(2)
            url = link_match.group(3)
            text_object.type = RichTextObject.TYPE_LINK
            text_object.url = url
            return self._create_styled_text_object(styled_text=link_text, text_object=text_object)

        if root_node:
            raise ValueError(
                f"Invalid styled text: {styled_text} did not match any styles")

        # Plain text.
        text_object.text = styled_text
        return text_object


if __name__ == "__main__":

    # Test cases for testing inline element converstion to text_objects.
    # TODO: Move to unit test module to maintain the parser algorithm.

    # markdown_text = '1. [What](http://link.com) a link\n2. I am trying ~~***something***~~ simple.\n\n\nok'
    # markdown_text = 'ok this i***s ***[***just***](http://www.google.com) a\n\ns ~~new~~ sectio**n o**k\n\na`nd` ***thenw*** h*a*t'
    # markdown_text = '> formatting ~~inside~~ quote\n> \n> lets see ***`how it`*** looks like\n> \n> k'
    # markdown_text = '```\n\n\nok bro\n```'
    # markdown_text = '* *bullet* 1\n* bullet **2**\n1. bullet number 1\n2. bullet number 2\n> block [quote 1](http://www.google.com)\n> [block](http://another%20link) quote 2\n\n```\n\ncode block 1\ncode block 2\n\ncode block 3\n```\n* bullet again'
    # markdown_text = '> Block a\n> \n> block between\n> Block b\n\n> Block C\n> Block D'
    # markdown_text = "quoting something now\n\n> What is this? \n> \n> We don't know the answer.\n\n* Take a leap of faith.\n* And try\nnew section again"
    # markdown_text = '1. More complex list\n2. Another one\n    1. Three\n    2. Four [things](http://www.google.com) `that are` ~~messed~~ up\n        1. woops ***i got*** it\n\n\n1. Five\n    * Six\n    * Seven\n2. Eight'
    # markdown_text = 'ok test italicizing\n1. hello bro\n\ndone\n\n* bullet'
    markdown_text = 'ok with quote **also**\n> hello\n\nok with ~~*preformatted*~~\n```\ncode block preformatted\n```\n* bullet bro'
    # markdown_text = 'There is another thing we want to test\n1. hello ~~in between~~ ~~buik ~~~~*brother*~~ sister\n2. This [is ](http://www.google.com)[***a***](http://www.google.com) list\n    1. Sub list\n    2. Sub list <b>\n3. Thsi is the third elem\n\nWhat about unordered list:\n* Ek\n* Do'

    # This is the most complex example that we should definitely keep in the unit tests
    # markdown_text = "**What is a DM?**\n\nDM is a `gimme code` ***Direct Message***. It's like a private 1:1 conversation between 2 people.\n\nHere is a code block:\n\n```\nx = 5\nx += 1\n```\n\nWhat about a list now?\n1. One\n    1. Two\n        1. Three\n            1. Four\n                1. Five\n            2. [Link mama](http://www.slack.com)\n2. Six\n    1. Seven\n* Bullet one\n    * Bullet 2\n        * Bullet 3\n\n> I'm being *blocking* from day 1\n> ok bro"
    # print(repr(markdown_text.split("\n")))
    # print("\n\n")

    # pprint.pprint(markdown_text)
    # rich_text_block = MarkdownToRichTextConverter().convert(markdown_text=markdown_text)
    # pprint.pprint(rich_text_block.model_dump(exclude_none=True))
    print(MarkdownToRichTextConverter().get_html(
        markdown_text=markdown_text))
