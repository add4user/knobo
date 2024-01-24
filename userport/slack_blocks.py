from pydantic import BaseModel, validator, root_validator
from typing import List, Dict, Optional, ClassVar

"""
Module that contains the different Slack Blocks classes which are components
used to create visually rich and interactive messages.

Reference: https://api.slack.com/reference/block-kit/blocks
"""


class RichTextObject(BaseModel):
    """
    Rich text object that can contain link and styling.
    """
    TYPE_TEXT: ClassVar[str] = 'text'
    TYPE_LINK: ClassVar[str] = 'link'

    class TextStyle(BaseModel):
        bold: Optional[bool] = None
        italic: Optional[bool] = None
        code: Optional[bool] = None
        strike: Optional[bool] = None

        @root_validator(pre=True)
        def any_of(cls, values):
            if not any(values):
                raise ValueError('One of bold, italic or code have a value')
            return values

    type: str
    text: str
    style: Optional[TextStyle] = None
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

    def get_markdown(self) -> str:
        """
        Return text formatted as Markdown.
        """
        text_val = self.text

        # Apply styling if any.
        if self.style:
            if self.style.bold:
                text_val = f'**{text_val}**'
            if self.style.italic:
                text_val = f'*{text_val}*'
            if self.style.code:
                text_val = f'`{text_val}`'
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

    type: str
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

    type: str
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
        elif self.style == RichTextListElement.STYLE_ORDERED:
            text_values = self._get_bullet_list_markdown()
        return "\n".join(text_values)


class RichTextPreformattedElement(BaseModel):
    """
    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text_preformatted
    """
    TYPE_VALUE: ClassVar[str] = 'rich_text_preformatted'
    type: str
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
    type: str
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
            text = f'> {elem}'
            text_values.append(text)
        return "".join(text_values)


class RichTextElement(BaseModel):
    """
    Class representing Rich Text Element.

    Type can be one of: rich_text_section, rich_text_list, rich_text_preformatted, and rich_text_quote.

    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text
    """
    type: str
    # The exact type of the dictionary depends on the type of element.
    elements: List[Dict]

    @validator("type")
    def validate_type(cls, v):
        if v not in set([RichTextSectionElement.TYPE_VALUE, RichTextListElement.TYPE_VALUE, RichTextPreformattedElement.TYPE_VALUE, RichTextQuoteElement.TYPE_VALUE]):
            raise ValueError(f"Expected rich_text element types, got {v}")
        return v

    def is_section(self) -> bool:
        return self.type == RichTextSectionElement.TYPE_VALUE

    def is_list(self) -> bool:
        return self.type == RichTextListElement.TYPE_VALUE

    def is_preformatted(self) -> bool:
        return self.type == RichTextPreformattedElement.TYPE_VALUE

    def is_quote(self) -> bool:
        return self.type == RichTextQuoteElement.TYPE_VALUE


class RichTextBlock(BaseModel):
    """
    Class representing Rich Text Block.

    Reference: https://api.slack.com/reference/block-kit/blocks#rich_text
    """
    TYPE_VALUE: ClassVar[str] = 'rich_text'
    type: str
    elements: List[RichTextElement]

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
        for elem in self.elements:
            text: str
            if elem.is_section():
                text = RichTextSectionElement(
                    **elem.model_dump()).get_markdown()
            elif elem.is_list():
                text = RichTextListElement(**elem.model_dump()).get_markdown()
            elif elem.is_preformatted():
                text = RichTextPreformattedElement(
                    **elem.model_dump()).get_markdown()
            elif elem.is_quote():
                text = RichTextQuoteElement(
                    **elem.model_dump()).get_markdown()
            else:
                raise ValueError(
                    f"Rich Text Element Type cannot be converted to markdown: {elem}")
            text_values.append(text)
        return "\n".join(text_values)
