from bs4 import BeautifulSoup, NavigableString, Tag
from typing import List, Optional, Dict
from pydantic import BaseModel
import userport.utils
from urllib.parse import urljoin


class SlackHTMLSection(BaseModel):
    """
    Container for holding section information
    like heading (Markdown formatted), body (Markdown formatted),
    parent and child ids. 
    """
    id: int
    heading_level: int
    heading: str = ""
    text: str = ""
    parent_id: Optional[int] = None
    child_ids: List[int] = []


class ListElem(BaseModel):
    """
    Formatting for list element.
    """
    ordered: bool = False
    bullet: bool = False
    offset: int = 0
    indent_spaces: int = 0


class TextFormatting(BaseModel):
    """
    Captures block and inline styles that are applied 
    to a piece of text inside HTML.
    More than one attribute can be true.
    """
    # Block styles.
    heading: bool = False
    list_element: bool = False
    cur_lists: List[ListElem] = []

    preformatted: bool = False
    blockquote: bool = False
    # Text associated with blockquote to make conversion
    # to markdown easier.
    blockquote_text: str = ""

    # Inline styles.
    bold: bool = False
    italic: bool = False
    code: bool = False
    strike: bool = False
    link: bool = False
    url: str = ""
    # Page URL provided by the user, it is used
    # to construct absolute URLs if <a> tags have
    # relative paths.
    page_url: str = ""

    def apply(self, text: str) -> str:
        """
        Apply current formatting to given text.
        The return string is Markdown formatted.
        """
        if self.preformatted:
            return text

        # We want to replace '\n' within HTML with empty string
        # otherwise formatting is off.
        text = text.replace('\n', '')

        if self.code:
            text = f'`{text}`'

        if self.bold:
            text = f'**{text}**'

        if self.italic:
            text = f'*{text}*'

        if self.strike:
            text = f'~~{text}~~'

        if self.link:
            assert self.url != "", 'URL cannot be empty when link is True'
            assert self.page_url != "", "Page URL cannot be empty when link is True"
            absolute_url: str = urljoin(self.page_url, self.url)
            text = f'[{text}]({absolute_url})'

        return text


class SlackHTMLParser:
    """
    Class to parse HTML into a Slack Sections contained in a single page.

    The heading and text in each section will be formatted in
    Markdown.
    """
    H1_TAG = 'h1'
    H2_TAG = 'h2'
    H3_TAG = 'h3'
    H4_TAG = 'h4'
    P_TAG = 'p'
    OL_TAG = 'ol'
    UL_TAG = 'ul'
    LI_TAG = 'li'
    BLOCKQUOTE_TAG = 'blockquote'
    PRE_TAG = 'pre'
    BOLD_TAG = 'b'
    STRONG_TAG = 'strong'
    EM_TAG = 'em'
    STRIKE_TAG = 'del'
    CODE_TAG = 'code'
    LINK_TAG = 'a'
    BREAK_TAG = 'br'
    HREF_ATTR = 'href'

    LIST_INDENT_DELTA = 4

    def parse(self, html_page: str, page_url: str, content_start_class: str = None):
        self.soup = BeautifulSoup(html_page, 'html.parser')
        self.page_url: str = page_url
        self.starting_htag: str = self._starting_heading_tag()
        self.start_parsing: bool = False
        self.end_parsing: bool = False
        self.next_id: int = 0
        self.root_section: SlackHTMLSection = None
        self.current_section: SlackHTMLSection = None
        self.cur_format = TextFormatting(page_url=self.page_url)
        self.all_sections_dict: Dict[int, SlackHTMLSection] = {}

        # If content start class is provided, we find tag associated with
        # it and use it as starting point for parsing the content.
        # If not provided or tag is None, we will use <body> as start tag.
        start_tag: Tag = self.soup.body
        if content_start_class:
            found_tag = self.soup.find(class_=content_start_class)
            if found_tag:
                start_tag = found_tag

        self._dfs_(start_tag)

    def get_root_section(self) -> SlackHTMLSection:
        """
        Return Root section.
        """
        return self.root_section

    def get_section_map(self) -> Dict[int, SlackHTMLSection]:
        """
        Return dictionary of parsed section ID to Section.
        """
        return self.all_sections_dict

    def _dfs_(self, tag: Tag):
        """
        Perform DFS over tags to parse section information.
        """
        if self.end_parsing:
            # Do nothing.
            return

        if not self.start_parsing:
            if tag.name == self.starting_htag:
                self.start_parsing = True

        if not self.start_parsing:
            self._parse_children(tag=tag)
            return

        if self.is_end_of_content(tag):
            self.end_parsing = True
            return

        self._parse_tag(tag=tag)

    def _parse_tag(self, tag: Tag):
        """
        Parse given tag and store if needed into sections.
        """
        if isinstance(tag, NavigableString):
            assert self.current_section, f"Current Section cannot be None for string: {tag}"
            formatted_text: str = self.cur_format.apply(text=str(tag))
            if self.cur_format.blockquote:
                self.cur_format.blockquote_text += formatted_text
            elif self.cur_format.heading:
                self.current_section.heading += formatted_text
            else:
                self.current_section.text += formatted_text
            return

        # Handle block elements.

        if self._is_heading_tag(tag):
            # Create new section and append to parent.
            heading_level: int = self._get_heading_level(tag)
            new_section = SlackHTMLSection(
                id=self.next_id, heading_level=heading_level)
            self.next_id += 1
            parent_section = self._get_parent_section(tag)
            if not parent_section:
                self.root_section = new_section
            else:
                # Update parent child relationships.
                new_section.parent_id = parent_section.id
                parent_section.child_ids.append(new_section.id)

            # update current section to new section.
            self.all_sections_dict[new_section.id] = new_section
            self.current_section = new_section

            # Apply formatting.
            self.cur_format.heading = True
            heading_prefix = userport.utils.convert_to_markdown_heading(
                text='', level=heading_level)
            self.current_section.heading = heading_prefix

            self._parse_children(tag)

            # Remove formatting.
            self.cur_format.heading = False
            return

        assert self.current_section, f'Current section cannot be None for paragraph tag: {tag}'

        if self._is_paragraph_tag(tag):
            if not self.cur_format.list_element:
                # Append newline only if not inside a <li> tag.
                self.current_section.text += "\n"
            self._parse_children(tag)
            return

        if self._is_ordered_list_tag(tag):
            # Add newline before appending text in children.
            self.current_section.text += "\n"

            list_str = ListElem(ordered=True, offset=1,
                                indent_spaces=self._get_indent_for_new_list())
            self.cur_format.cur_lists.append(list_str)

            self._parse_children(tag)

            self.cur_format.cur_lists.pop()
            return

        if self._is_bullet_list_tag(tag):
            # Add newline before appending text in children.
            self.current_section.text += "\n"

            list_str = ListElem(
                bullet=True, indent_spaces=self._get_indent_for_new_list())
            self.cur_format.cur_lists.append(list_str)

            self._parse_children(tag)

            self.cur_format.cur_lists.pop()
            return

        if self._is_list_tag(tag):
            # Add newline before appending text in children.
            self.current_section.text += "\n"

            self.cur_format.list_element = True
            self.current_section.text += self._get_list_prefix_str()

            self._parse_children(tag)

            self.cur_format.list_element = False
            # Update offset for last elem in ordered list.
            if self.cur_format.cur_lists[-1].ordered:
                self.cur_format.cur_lists[-1].offset += 1

            return

        if self._is_preformatted_tag(tag):
            self.current_section.text += "\n```\n"
            self.cur_format.preformatted = True

            self._parse_children(tag)

            self.cur_format.preformatted = False
            self.current_section.text += "\n```\n"
            return

        if self._is_blockquote_tag(tag):
            self.current_section.text += "\n"
            self.cur_format.blockquote = True
            self.cur_format.blockquote_text = ""

            self._parse_children(tag)

            # convert blockquote_text to markdown text.
            formatted_lines: List[str] = []
            for line in self.cur_format.blockquote_text.split("\n"):
                formatted_lines.append(f'> {line}')
            markdown_blockquote_text = "\n".join(formatted_lines)
            self.current_section.text += markdown_blockquote_text

            self.cur_format.blockquote = False
            self.cur_format.blockquote_text = ""
            return

        # Handle inline elements.

        if self._is_bold_tag(tag):
            self.cur_format.bold = True

            self._parse_children(tag)

            self.cur_format.bold = False
            return

        if self._is_italic_tag(tag):
            self.cur_format.italic = True

            self._parse_children(tag)

            self.cur_format.italic = False
            return

        if self._is_strike_tag(tag):
            self.cur_format.strike = True

            self._parse_children(tag)

            self.cur_format.strike = False
            return

        if self._is_code_tag(tag):
            self.cur_format.code = True

            self._parse_children(tag)

            self.cur_format.code = False
            return

        if self._is_link_tag(tag):
            self.cur_format.link = True
            self.cur_format.url = tag[self.HREF_ATTR]

            self._parse_children(tag)

            self.cur_format.link = False
            self.cur_format.url = ""
            return

        if self._is_break_tag(tag):
            # Just append a new line.
            self.current_section.text += "\n"
            return

        # If no tag has matched, parse children anyways.
        self._parse_children(tag)

    def _parse_children(self, tag: Tag):
        """
        Helper to parse children of given tag.
        """
        if isinstance(tag, NavigableString):
            # This is when parsing has not started.
            return
        for child_tag in tag.children:
            self._dfs_(child_tag)

    def _starting_heading_tag(self):
        """
        Returns first of h1,h2, h3 or h4 tags in HTML page.
        If none found, throws an error.
        """
        if self.soup.find(self.H1_TAG):
            return self.H1_TAG
        elif self.soup.find(self.H2_TAG):
            return self.H2_TAG
        elif self.soup.find(self.H3_TAG):
            return self.H3_TAG
        elif self.soup.find(self.H4_TAG):
            return self.H4_TAG

        raise ValueError('Error! No heading tags found in document')

    def _get_parent_section(self, htag: Tag) -> Optional[SlackHTMLSection]:
        """
        Return parent section for current heading tag.
        Can be only be None when root section does not exist already.
        """
        assert self._is_heading_tag(htag), f"Expected heading tag, got {htag}"
        parent_section = self.current_section
        tag_heading_level = self._get_heading_level(htag)
        while parent_section and parent_section.heading_level >= tag_heading_level:
            if parent_section == self.root_section:
                # This is the top most section, so we will make it the parent in this case.
                return parent_section
            parent_section = self.all_sections_dict[parent_section.parent_id]
        if self.root_section and not parent_section:
            raise ValueError(
                f"Parent section for {htag} cannot be None with existing root section: {self.root_section}")
        return parent_section

    def _is_heading_tag(self, tag: Tag) -> bool:
        return tag.name.startswith('h')

    def _is_paragraph_tag(self, tag: Tag) -> bool:
        return tag.name == self.P_TAG

    def _is_ordered_list_tag(self, tag: Tag) -> bool:
        return tag.name == self.OL_TAG

    def _is_bullet_list_tag(self, tag: Tag) -> bool:
        return tag.name == self.UL_TAG

    def _is_preformatted_tag(self, tag: Tag) -> bool:
        return tag.name == self.PRE_TAG

    def _is_blockquote_tag(self, tag: Tag) -> bool:
        return tag.name == self.BLOCKQUOTE_TAG

    def _is_list_tag(self, tag: Tag) -> bool:
        return tag.name == self.LI_TAG

    def _is_bold_tag(self, tag: Tag) -> bool:
        return tag.name in set([self.BOLD_TAG, self.STRONG_TAG])

    def _is_italic_tag(self, tag: Tag) -> bool:
        return tag.name == self.EM_TAG

    def _is_strike_tag(self, tag: Tag) -> bool:
        return tag.name == self.STRIKE_TAG

    def _is_code_tag(self, tag: Tag) -> bool:
        return tag.name == self.CODE_TAG

    def _is_link_tag(self, tag: Tag) -> bool:
        return tag.name == self.LINK_TAG and self.HREF_ATTR in tag.attrs

    def _is_break_tag(self, tag: Tag) -> bool:
        return tag.name == self.BREAK_TAG

    def _get_heading_level(self, htag: Tag) -> int:
        """
        Return level of given heading tag.
        """
        assert self._is_heading_tag(htag), f"Expected heading tag, got {htag}"
        return int(htag.name[1:])

    def _get_indent_for_new_list(self) -> int:
        """
        Return indentation spaces for newly created list
        based on existing lists.
        """
        prev_indent_spaces: int = 0 if len(
            self.cur_format.cur_lists) == 0 else self.cur_format.cur_lists[-1].indent_spaces
        return prev_indent_spaces + self.LIST_INDENT_DELTA

    def _get_list_prefix_str(self) -> str:
        """
        Get prefix string for <li> element based on the current list.
        """
        cur_list_elem: ListElem = self.cur_format.cur_lists[-1]
        indentation_str = cur_list_elem.indent_spaces * ' '
        list_str = ""
        if cur_list_elem.bullet:
            list_str = "*"
        elif cur_list_elem.ordered:
            list_num: int = cur_list_elem.offset
            list_str = f"{list_num}."
        else:
            raise ValueError(
                f'Expected bullet or ordered list, got {cur_list_elem}')

        return f'{indentation_str}{list_str} '

    def is_end_of_content(self, tag: Tag) -> bool:
        """
        There are few ways we detect end of content. If any of these conditions
        is met, we end parsing:
        [1] footer as tag or within tag attributes signals end of parsing main content.
        [2] script tag encountered after parsing is started i.e. script tag in body indicates no more content to follow usually.
        TODO: Come up with better algorithm in the future.
        """
        if isinstance(tag, NavigableString):
            return False
        footer_keyword = 'footer'
        script_keyword = 'script'
        if tag == footer_keyword or tag == script_keyword:
            return True

        for attr in tag.attrs:
            if attr != "class":
                continue
            values = tag[attr]
            if not values:
                continue
            if footer_keyword in set(values):
                return True

        return False


if __name__ == "__main__":
    # url = 'https://flask.palletsprojects.com/en/2.3.x/patterns/celery/'
    # url = 'https://flask.palletsprojects.com/en/2.3.x/installation/#install-flask'
    # url = 'https://flask.palletsprojects.com/en/2.3.x/tutorial/factory/'
    url = 'https://slack.com/intl/en-gb/help/articles/360017938993-What-is-a-channel'
    html_page = userport.utils.fetch_html_page(url)

    parser = SlackHTMLParser()
    parser.parse(html_page=html_page, page_url=url,
                 content_start_class='content_col')

    root_section = parser.get_root_section()
    # print(root_section.child_ids)
    section_map = parser.get_section_map()
    child_section = section_map[root_section.child_ids[2]]
    # grandchild_section = section_map[child_section.child_ids[0]]
    section = child_section
    print(f'{section.heading}\n{section.text}')
