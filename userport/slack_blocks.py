from pydantic import BaseModel, validator, root_validator, ConfigDict
from typing import List, Dict, Optional, ClassVar, Union

"""
Module that contains the different Slack Blocks classes which are components
used to create visually rich and interactive messages.

Reference: https://api.slack.com/reference/block-kit/blocks
"""


class TextObject(BaseModel):
    """
    Represents plain or markdown text object. Use RichTextObject if validating text from Slack's WYSIWYG editor.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#text
    """
    TYPE_PLAIN_TEXT: ClassVar[str] = 'plain_text'
    TYPE_MARKDOWN: ClassVar[str] = 'mrkdwn'

    type: str
    text: str
    # Emoji cannot be set when type is 'mrkdwn'.
    emoji: Optional[bool] = None

    @validator("type")
    def validate_type(cls, v):
        if v not in set([TextObject.TYPE_PLAIN_TEXT, TextObject.TYPE_MARKDOWN]):
            raise ValueError(
                f"Expected {TextObject.TYPE_PLAIN_TEXT} or {TextObject.TYPE_MARKDOWN} type, got {v}")
        return v


class RichTextStyle(BaseModel):
    """
    Rich text style for inline element styling.
    """
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    code: Optional[bool] = None
    strike: Optional[bool] = None


class RichTextObject(BaseModel):
    """
    Rich text object that can contain link and styling.
    """
    TYPE_TEXT: ClassVar[str] = 'text'
    TYPE_LINK: ClassVar[str] = 'link'

    type: str
    text: str
    style: Optional[RichTextStyle] = None
    url: Optional[str] = None

    @validator("type")
    def validate_type(cls, v):
        if v not in set([RichTextObject.TYPE_TEXT, RichTextObject.TYPE_LINK]):
            raise ValueError(
                f"Expected {RichTextObject.TYPE_TEXT} or {RichTextObject.TYPE_LINK} type, got {v}")
        return v

    @root_validator(pre=True)
    def check_url_set_condition(cls, values):
        type_val = values.get('type')
        url_val = values.get('url')
        if type_val == RichTextObject.TYPE_LINK and url_val is None:
            raise ValueError(
                f'"url" attribute is not set even thought type is {RichTextObject.TYPE_LINK}')
        return values

    def is_plain_text(self) -> bool:
        """
        Returns True if text is plain (no formatting) else False.
        """
        return self.style == None and self.type == RichTextObject.TYPE_TEXT

    def get_markdown(self) -> str:
        """
        Return text formatted as Markdown.
        """
        text_val = self.text

        # Apply styling if any.
        if self.style:
            if self.style.code:
                text_val = f'`{text_val}`'
            if self.style.bold:
                text_val = f'**{text_val}**'
            if self.style.italic:
                text_val = f'*{text_val}*'
            if self.style.strike:
                text_val = f'~~{text_val}~~'

        # Add URL if any.
        if self.type == RichTextObject.TYPE_LINK:
            text_val = f'[{text_val}]({self.url})'
        return text_val

    def get_html(self, preformatted: bool = False) -> str:
        """
        Returns text formatted as HTML.

        If part of preformatted block, just return text as is.
        """
        text_val = self.text

        # Replace newlines with <br> for line breaks.
        text_val = text_val.replace("\n", "<br>")

        if preformatted:
            return text_val

        if self.style:
            if self.style.code:
                text_val = f'<code style="color:#f59b3a;background-color:#faf4f4">{text_val}</code>'
            if self.style.bold:
                text_val = f'<strong>{text_val}</strong>'
            if self.style.italic:
                text_val = f'<em>{text_val}</em>'
            if self.style.strike:
                text_val = f'<del>{text_val}</del>'

        # Add URL if any.
        if self.type == RichTextObject.TYPE_LINK:
            text_val = f'<a href="{self.url}" target="_blank">{text_val}</a>'

        return text_val


class RichTextSectionElement(BaseModel):
    """
    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text_section
    """
    TYPE_VALUE: ClassVar[str] = 'rich_text_section'

    type: str = TYPE_VALUE
    elements: List[RichTextObject]

    @validator("type")
    def validate_type(cls, v):
        if v != RichTextSectionElement.TYPE_VALUE:
            raise ValueError(
                f"Expected rich_text_section element type, got {v}")
        return v

    def get_markdown(self) -> str:
        """
        Return text formatted as Markdown.
        """
        text_values: List[str] = []
        for elem in self.elements:
            text_values.append(elem.get_markdown())
        return "".join(text_values)

    def get_html(self) -> str:
        """
        Returns text formatted as HTML.
        """
        text_values: List[str] = []
        for elem in self.elements:
            text_values.append(elem.get_html())
        res_text = "".join(text_values)
        return f'<p>{res_text}</p>'


class RichTextListElement(BaseModel):
    """
    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text_list
    """
    TYPE_VALUE: ClassVar[str] = 'rich_text_list'
    STYLE_BULLET: ClassVar[str] = 'bullet'
    STYLE_ORDERED: ClassVar[str] = 'ordered'

    type: str = TYPE_VALUE
    style: str
    elements: List[RichTextSectionElement]
    border: Optional[int] = None
    indent: Optional[int] = None
    offset: Optional[int] = None

    @validator("type")
    def validate_type(cls, v):
        if v != RichTextListElement.TYPE_VALUE:
            raise ValueError(
                f"Expected rich_text_list element type, got {v}")
        return v

    @validator("style")
    def validate_style(cls, v):
        if v not in set([RichTextListElement.STYLE_BULLET, RichTextListElement.STYLE_ORDERED]):
            raise ValueError(
                f"Expected rich_text_list 'style' attribute to be {RichTextListElement.STYLE_BULLET} or {RichTextListElement.STYLE_ORDERED}, got {v}")
        return v

    def _get_indent_multiplier(self) -> int:
        """
        Return indent multiplier.
        """
        return self.indent if self.indent else 0

    def _get_indentation(self) -> str:
        """
        Return indentation string based on indent multiplier.
        This string string will be prefixed to the list element.
        """
        return 4 * self._get_indent_multiplier() * " "

    def _get_ordered_list_markdown(self) -> List[str]:
        """
        Return ordered text list formatted as markdown.
        """
        text_values: List[str] = []
        current_offset: int = self.offset + 1 if self.offset else 1
        for elem in self.elements:
            text = f'{self._get_indentation()}{current_offset}. {elem.get_markdown()}'
            text_values.append(text)
            current_offset += 1
        return text_values

    def _get_bullet_list_markdown(self) -> List[str]:
        """
        Return bulleted text list formatted as markdown.
        """
        text_values: List[str] = []
        for elem in self.elements:
            text = f'{self._get_indentation()}* {elem.get_markdown()}'
            text_values.append(text)
        return text_values

    def get_markdown(self) -> str:
        """
        Return text formatted as Markdown.
        """
        text_values: List[str] = []
        if self.is_ordered_list():
            text_values = self._get_ordered_list_markdown()
        elif self.is_bullet_list():
            text_values = self._get_bullet_list_markdown()
        return "\n".join(text_values)

    def is_ordered_list(self) -> bool:
        """
        Returns True if ordered list and False otherwise.
        """
        return self.style == RichTextListElement.STYLE_ORDERED

    def is_bullet_list(self) -> bool:
        """
        Returns True if bullet list and False otherwise.
        """
        return self.style == RichTextListElement.STYLE_BULLET


class RichTextPreformattedElement(BaseModel):
    """
    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text_preformatted
    """
    TYPE_VALUE: ClassVar[str] = 'rich_text_preformatted'
    type: str = TYPE_VALUE
    border: int
    elements: List[RichTextObject]

    @validator("type")
    def validate_type(cls, v):
        if v != RichTextPreformattedElement.TYPE_VALUE:
            raise ValueError(
                f"Expected {RichTextPreformattedElement.TYPE_VALUE} element type, got {v}")
        return v

    def get_markdown(self) -> str:
        """
        Return text formatted as Markdown.
        """
        text_values: List[str] = []
        for elem in self.elements:
            text = f'```\n{elem.get_markdown()}\n```'
            text_values.append(text)
        return "".join(text_values)

    def get_html(self) -> str:
        """
        Return text formatted as HTML.
        """
        text_values: List[str] = []
        for elem in self.elements:
            text = f'<code>{elem.get_html(preformatted=True)}</code>'
            text_values.append(text)
        return f'<pre style="background-color:lightgray;">{"".join(text_values)}</pre>'


class RichTextQuoteElement(BaseModel):
    """
    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text_quote
    """
    TYPE_VALUE: ClassVar[str] = 'rich_text_quote'
    type: str = TYPE_VALUE
    border: Optional[int] = None
    elements: List[RichTextObject]

    @validator("type")
    def validate_type(cls, v):
        if v != RichTextQuoteElement.TYPE_VALUE:
            raise ValueError(
                f"Expected {RichTextQuoteElement.TYPE_VALUE} element type, got {v}")
        return v

    def get_markdown(self) -> str:
        """
        Return text formatted as Markdown.
        """
        text_values: List[str] = []
        for elem in self.elements:
            text_values.append(elem.get_markdown())
        text_with_markdown = "".join(text_values)

        # Split markdown text by new lines and prepend > for each line.
        final_formatted_lines: List[str] = []
        for line in text_with_markdown.split("\n"):
            final_formatted_lines.append(f"> {line}")
        return "\n".join(final_formatted_lines)

    def get_html(self) -> str:
        """
        Return text formatted as HTML.
        """
        text_values: List[str] = []
        for elem in self.elements:
            text_values.append(elem.get_html())
        final_text = "".join(text_values)
        return f"<blockquote style='border-left: 10px solid #ccc;margin: 1.5em 10px;padding: 0.5em 10px;'>{final_text}</blockquote>"


class RichTextBlock(BaseModel):
    """
    Class representing Rich Text Block.

    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text
    """
    TYPE_VALUE: ClassVar[str] = 'rich_text'
    type: str = TYPE_VALUE
    elements: List[Union[RichTextSectionElement, RichTextListElement,
                         RichTextPreformattedElement, RichTextQuoteElement]]
    block_id: Optional[str] = None

    @validator("type")
    def validate_type(cls, v):
        if v != RichTextBlock.TYPE_VALUE:
            raise ValueError(
                f"Expected {RichTextBlock.TYPE_VALUE} as type value, got {v}")
        return v

    def get_markdown(self) -> str:
        """
        Return text formatted as Markdown.
        """
        text_values: List[str] = []
        for i, elem in enumerate(self.elements):
            text: str
            if isinstance(elem, RichTextSectionElement):
                text = RichTextSectionElement(
                    **elem.model_dump()).get_markdown()
            elif isinstance(elem, RichTextListElement):
                text = RichTextListElement(
                    **elem.model_dump()).get_markdown()
            elif isinstance(elem, RichTextPreformattedElement):
                # Unlike Section Element, a trailing \n has to be added manually so we can get the correct
                # final string when we combine all section elements.
                text = RichTextPreformattedElement(
                    **elem.model_dump()).get_markdown()
            elif isinstance(elem, RichTextQuoteElement):
                # Unlike Section Element, a trailing \n has to be added manually so we can get the correct
                # final string when we combine all section elements.
                text = RichTextQuoteElement(
                    **elem.model_dump()).get_markdown()
            else:
                raise ValueError(
                    f"Rich Text Element Type cannot be converted to markdown: {elem}")

            if (i != len(self.elements) - 1) and \
                    (isinstance(elem, RichTextListElement) or
                     isinstance(elem, RichTextPreformattedElement) or
                     isinstance(elem, RichTextQuoteElement)):
                # Unlike Section Element, a trailing \n has to be added manually to other types of elements
                # so we can get the correct final string when we combine all section elements.
                # We do this only if this element is not the final element.
                text = text + "\n"

            text_values.append(text)
        return "".join(text_values)

    def get_html(self) -> str:
        """
        Return text formatted as HTML.
        """
        current_list_of_lists: List[RichTextListElement] = []
        html_values = []
        for elem in self.elements:
            if isinstance(elem, RichTextSectionElement) or \
                isinstance(elem, RichTextPreformattedElement) or \
                    isinstance(elem, RichTextQuoteElement):
                if len(current_list_of_lists) > 0:
                    # Compute HTML and reset the list.
                    html_values.append(
                        self._get_html_from_list_of_lists(current_list_of_lists))
                    current_list_of_lists = []
                html_values.append(elem.get_html())
            elif isinstance(elem, RichTextListElement):
                current_list_of_lists.append(elem)
            else:
                raise ValueError(
                    f"Invalid instance of element: {elem} cannot be converted to HTML")

        # Close remaining open lists.
        if len(current_list_of_lists) > 0:
            # Compute HTML and reset the list.
            html_values.append(
                self._get_html_from_list_of_lists(current_list_of_lists))
            current_list_of_lists = []
        return "".join(html_values)

    def _get_html_from_list_of_lists(self, list_of_lists: List[RichTextListElement]) -> str:
        """
        Helper to return HTML text for given list of rich text list elements.
        """
        assert len(list_of_lists) > 0, "Expected list of lists to not be empty"

        first_list = list_of_lists[0]
        html_values: List[str] = [self._create_new_open_list_html(first_list)]
        open_lists: List[RichTextListElement] = [first_list]
        for i in range(1, len(list_of_lists)):
            cur_list = list_of_lists[i]
            last_list = open_lists[-1]

            if cur_list.indent > last_list.indent:
                # Create a new list.
                html_values.append(self._create_new_open_list_html(cur_list))
                open_lists.append(cur_list)
            else:
                # Close all open lists that have larger indentation and add
                # to the list with same indentation.
                while len(open_lists) > 0:
                    open_list_elem: RichTextListElement = open_lists[-1]
                    if open_list_elem.indent > cur_list.indent:
                        # Close this list.
                        close_tag = '</ol>' if open_list_elem.is_ordered_list() else '</ul>'
                        html_values.append(f"</li>{close_tag}")
                        open_lists.pop()
                    elif open_list_elem.indent == cur_list.indent:
                        if open_list_elem.style != cur_list.style:
                            # List style different at the same indentation, close the old one.
                            close_tag = '</ol>' if open_list_elem.is_ordered_list() else '</ul>'
                            html_values.append(f"</li>{close_tag}")
                            open_lists.pop()

                            # Create new list.
                            html_values.append(self._create_new_open_list_html(
                                cur_list, create_open_tag=True))
                            open_lists.append(cur_list)
                        else:
                            # Add to existing list.
                            html_values.append(self._create_new_open_list_html(
                                cur_list, create_open_tag=False))
                        break

        # Close any remaining open lists.
        while len(open_lists) > 0:
            open_list_elem: RichTextListElement = open_lists.pop()
            close_tag = '</ol>' if open_list_elem.is_ordered_list() else '</ul>'
            html_values.append(f"</li>{close_tag}")

        return "".join(html_values)

    def _create_new_open_list_html(self, list_elem: RichTextListElement, create_open_tag: bool = True) -> str:
        """
        Returns HTML creating a new list and leaving the list open.
        """
        open_tag = '<ol>' if list_elem.is_ordered_list() else '<ul>'
        list_text_values: List[str] = []
        if create_open_tag:
            list_text_values.append(open_tag)

        for i in range(0, len(list_elem.elements)-1):
            sec_elem: RichTextSectionElement = list_elem.elements[i]
            list_text = f'<li>{sec_elem.get_html()}</li>'
            list_text_values.append(list_text)

        # Final element leave <li> as open tag since it may be appended to in the next list.
        last_elem: RichTextSectionElement = list_elem.elements[-1]
        list_text_values.append(f'<li>{last_elem.get_html()}')
        return "".join(list_text_values)


class TextInputElement(BaseModel):
    """
    Class representing either Plain Text Input Element or Rich Text Input Element.

    References:
    1. https://api.slack.com/reference/block-kit/block-elements#input
    2. https://api.slack.com/reference/block-kit/block-elements#rich_text_input
    """
    PLAIN_TEXT_INPUT_VALUE: ClassVar[str] = "plain_text_input"
    RICH_TEXT_INPUT_VALUE: ClassVar[str] = "rich_text_input"

    type: str
    action_id: str
    initial_value: Union[str, RichTextBlock]

    @validator("type")
    def validate_type(cls, v):
        if v not in set([TextInputElement.PLAIN_TEXT_INPUT_VALUE, TextInputElement.RICH_TEXT_INPUT_VALUE]):
            raise ValueError(
                f"Expected {TextInputElement.PLAIN_TEXT_INPUT_VALUE} or {TextInputElement.RICH_TEXT_INPUT_VALUE} as type values, got {v}")
        return v


class PlainTextInputElement(TextInputElement):
    """
    Class representing either Plain Text Input Element.

    Reference: https://api.slack.com/reference/block-kit/block-elements#input
    """
    type: str = TextInputElement.PLAIN_TEXT_INPUT_VALUE
    initial_value: str = ""

    @validator("type")
    def validate_plain_text_type(cls, v):
        if v != TextInputElement.PLAIN_TEXT_INPUT_VALUE:
            raise ValueError(
                f"Expected {TextInputElement.PLAIN_TEXT_INPUT_VALUE} as type value, got {v}")
        return v


class RichTextInputElement(TextInputElement):
    """
    Class representing either Rich Text Input Element.

    Reference: https://api.slack.com/reference/block-kit/block-elements#rich_text_input
    """
    type: str = TextInputElement.RICH_TEXT_INPUT_VALUE
    initial_value: RichTextBlock

    @validator("type")
    def validate_rich_text_type(cls, v):
        if v != TextInputElement.RICH_TEXT_INPUT_VALUE:
            raise ValueError(
                f"Expected {TextInputElement.RICH_TEXT_INPUT_VALUE} as type value, got {v}")
        return v


class SelectOptionObject(BaseModel):
    """
    Represents an Option object to be used with Select Menu Element.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#option
    """
    text: TextObject
    value: str

    def get_value(self) -> str:
        """
        Returns value associated with selection object.
        """
        return self.value


class SelectMenuStaticElement(BaseModel):
    """
    Class representing Select Menu element using static source as input.

    Reference: https://api.slack.com/reference/block-kit/block-elements#static_select
    """
    TYPE_VALUE: ClassVar[str] = 'static_select'

    type: str = TYPE_VALUE
    action_id: str
    options: List[SelectOptionObject]
    initial_option: Optional[SelectOptionObject] = None

    @validator("type")
    def validate_type(cls, v):
        if v != SelectMenuStaticElement.TYPE_VALUE:
            raise ValueError(
                f"Expected {SelectMenuStaticElement.TYPE_VALUE} as type value, got {v}")
        return v


class InputBlock(BaseModel):
    """
    Class representing Input Block.

    Reference: https://api.slack.com/reference/block-kit/blocks#input
    """
    TYPE_VALUE: ClassVar[str] = 'input'

    type: str = TYPE_VALUE
    label: TextObject
    block_id: str
    element: Union[TextInputElement, SelectMenuStaticElement]
    dispatch_action: bool = False

    @validator("type")
    def validate_type(cls, v):
        if v != InputBlock.TYPE_VALUE:
            raise ValueError(
                f"Expected {InputBlock.TYPE_VALUE} as type value, got {v}")
        return v


class HeaderBlock(BaseModel):
    """
    Class representing Header Block.

    Reference: https://api.slack.com/reference/block-kit/blocks#header
    """
    TYPE_VALUE: ClassVar[str] = 'header'

    type: str = TYPE_VALUE
    text: TextObject
    block_id: Optional[str] = None

    @validator("type")
    def validate_type(cls, v):
        if v != HeaderBlock.TYPE_VALUE:
            raise ValueError(
                f"Expected {HeaderBlock.TYPE_VALUE} as type value, got {v}")
        return v

    @validator("text")
    def validate_text(cls, v):
        text_obj: TextObject = v
        if text_obj.type != TextObject.TYPE_PLAIN_TEXT:
            raise ValueError(
                f"Expected {TextObject.TYPE_PLAIN_TEXT} as text object type, got {v}")
        return v


class DividerBlock(BaseModel):
    """
    Class representing Divider Block.

    Reference: https://api.slack.com/reference/block-kit/blocks#divider
    """
    TYPE_VALUE: ClassVar[str] = 'divider'

    type: str = TYPE_VALUE
    block_id: Optional[str] = None
