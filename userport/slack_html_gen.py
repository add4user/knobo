import userport.db
from userport.markdown_parser import MarkdownToRichTextConverter
from userport.slack_models import SlackSection
from userport.utils import get_heading_level_and_content, to_day_format, get_heading_content
from typing import List
from flask import url_for


class SlackHTMLGenerator:
    """
    Class to convert slack sections in a page to an HTML page.

    We cannot use Jinja2 engine directly because we have dynamic HTML
    element generation which will be autoescaped to a string by Jinja2. 

    We will instead generate HTML by string formatting manually.

    This is used by Flask endpoint to render documentation in HTML pages.
    """

    def __init__(self) -> None:
        self.template_path = 'userport/templates/slack_doc/page.html'
        self.stylesheet_url = url_for(
            'static', filename='slack_doc/style.css')
        self.markdown_converter = MarkdownToRichTextConverter()
        self.html_text = self._load_html_string(
            template_path=self.template_path)

    def get_page(self, team_domain: str, page_html_section_id: str) -> str:
        """
        Returns HTML page as text associated with given Team Domain and Page HTML Section.
        """
        page_index_html = self._get_page_index(team_domain=team_domain)
        page_html = self._get_page_content(
            team_domain=team_domain, page_html_section_id=page_html_section_id)

        # Render content in template.
        rendered_html = self.html_text.replace(
            '{{ page_index_html }}', page_index_html)
        # TODO: Instead of uppercasing the domain, fetch team name from Slack API.
        rendered_html = rendered_html.replace(
            '{{ team_name }}', team_domain.capitalize())
        rendered_html = rendered_html.replace('{{ page_html }}', page_html)
        rendered_html = rendered_html.replace(
            '{{ stylesheet_url }}', self.stylesheet_url)
        return rendered_html

    def _get_page_index(self, team_domain: str) -> str:
        """
        Helper to get index (sitemap) of page in HTML.

        This will be a list of <a> links that will be listed on the left pane of the page.
        """
        slack_pages: List[SlackSection] = userport.db.get_slack_pages_within_team(
            team_domain=team_domain)
        html_values: List[str] = []
        for page in slack_pages:
            html_section_id: str = page.html_section_id
            heading_content = get_heading_content(markdown_text=page.heading)
            a_tag = f'<a href="/{team_domain}/{html_section_id}" id="{html_section_id}">{heading_content}</a>'
            html_val = f'<li>{a_tag}</li>'
            html_values.append(html_val)

        page_index_html = "".join(html_values)
        return f'<ul>{page_index_html}</ul>'

    def _get_page_content(self, team_domain: str, page_html_section_id: str) -> str:
        """
        Helper to get content of HTML page.
        """
        slack_sections: List[SlackSection] = userport.db.get_ordered_slack_sections_in_page(
            team_domain=team_domain, page_html_section_id=page_html_section_id)

        html_values: List[str] = []
        for section in slack_sections:
            html_values.append(self._get_section_html(section))
        page_html = "".join(html_values)
        page_html = f'<div id="page-content">{page_html}</div>'
        return page_html

    def _get_section_html(self, section: SlackSection) -> str:
        """
        Return HTML for given slack section.
        """
        html_values: List[str] = []

        # Add heading HTML.
        heading_level, heading_content = get_heading_level_and_content(
            markdown_text=section.heading)
        heading_html = self._to_heading_html(
            heading_level=heading_level, heading_content=heading_content, heading_html_section_id=section.html_section_id)
        html_values.append(heading_html)

        # Add section HTML.
        if len(section.text) > 0:
            section_html: str = self.markdown_converter.get_html(
                markdown_text=section.text)
            html_values.append(section_html)

        # Add footer on who last updated this section.
        last_updated_time_str = to_day_format(
            datetime_obj=section.last_updated_time)
        last_updated_html = f'<p class="last-updated-info">Last Updated: {last_updated_time_str} by {section.updater_email}</p>'
        last_updated_html = f'<div class="last-updated-info-container">{last_updated_html}</div>'
        html_values.append(last_updated_html)

        return "".join(html_values)

    def _to_heading_html(self, heading_level: int, heading_content: str, heading_html_section_id: str) -> str:
        """
        Return HTML string for given heading level and content.
        """
        open_tag = f'<h{heading_level} id="{heading_html_section_id}">'
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
