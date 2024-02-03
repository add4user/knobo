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
                text_val = f'~{text_val}~'

        # Add URL if any.
        if self.type == RichTextObject.TYPE_LINK:
            text_val = f'[{text_val}]({self.url})'
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
        if self.style == RichTextListElement.STYLE_ORDERED:
            text_values = self._get_ordered_list_markdown()
        elif self.style == RichTextListElement.STYLE_BULLET:
            text_values = self._get_bullet_list_markdown()
        return "\n".join(text_values)


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


class SectionBlock(BaseModel):
    """
    Class representing Section Block.

    Reference: https://api.slack.com/reference/block-kit/blocks#section
    """
    TYPE_VALUE: ClassVar[str] = 'section'

    type: str = TYPE_VALUE
    text: TextObject
