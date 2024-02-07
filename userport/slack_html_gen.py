import userport.db
from userport.markdown_parser import MarkdownToRichTextConverter
from userport.slack_models import SlackSection
from userport.utils import get_heading_level_and_content
from typing import List


class SlackHTMLGenerator:
    """
    Class to convert slack sections in a page to an HTML page.

    We cannot use Jinja2 engine directly because we have dynamic HTML
    element generation which will be autoescaped to a string by Jinja2. 

    We will instead generate HTML by string formatting manually.
    """

    def __init__(self) -> None:
        self.template_path = 'userport/templates/slack_doc/page.html'
        self.markdown_converter = MarkdownToRichTextConverter()
        self.html_text = self._load_html_string(
            template_path=self.template_path)

    def get_page(self, team_domain: str, page_html_section_id: str) -> str:
        """
        Returns HTML page as text associated with given Team Domain and Page HTML Section.
        """
        slack_sections: List[SlackSection] = userport.db.get_ordered_slack_sections_in_page(
            team_domain=team_domain, page_html_section_id=page_html_section_id)

        html_values: List[str] = []
        for section in slack_sections:
            html_values.append(self._get_section_html(section))
        page_html = "".join(html_values)

        # Render content in template.
        return self.html_text.replace('{{ page_html }}', page_html)

    def _get_section_html(self, section: SlackSection) -> str:
        """
        Return HTML for given slack section.
        """
        html_values: List[str] = []

        # Add heading HTML.
        heading_level, heading_content = get_heading_level_and_content(
            markdown_text=section.heading)
        heading_html = self._to_heading_html(
            heading_level=heading_level, heading_content=heading_content)
        html_values.append(heading_html)

        # Add break to separate HTML from content.
        html_values.append('<br><br>')

        # Add section HTML.
        section_html: str = self.markdown_converter.get_html(
            markdown_text=section.text)
        html_values.append(section_html)

        return "".join(html_values)

    def _to_heading_html(self, heading_level: int, heading_content: str) -> str:
        """
        Return HTML string for given heading level and content.
        """
        open_tag = f'<h{heading_level}>'
        close_tag = f'</h{heading_level}>'
        return f'{open_tag}{heading_content}{close_tag}'

    def _load_html_string(self, template_path: str) -> str:
        """
        Load HTML string from Jinja template file.
        """
        with open(template_path, mode='r') as f:
            return f.read()


if __name__ == "__main__":
    SlackHTMLGenerator()
