from userport.utils import fetch_html_page
from userport.index.html_parser import parse_html
from userport.index.html_node import HTMLSection
from userport.text_analyzer import TextAnalyzer
from typing import List
from dataclasses import dataclass, field
from queue import Queue


@dataclass
class PageSection:
    """
    Final details of a page's section. Contains
    section text, summary, previous section summary
    and embedding of current section.
    """
    is_root: bool = False
    text: str = ""
    prev_sections_context: str = ""
    summary: str = ""
    summary_vector_embedding: List[float] = field(default_factory=list)
    proper_nouns_in_section: List[str] = field(default_factory=list)
    proper_nouns_in_doc: List[str] = field(default_factory=list)
    child_sections: List['PageSection'] = field(default_factory=list)


class PageSectionManager:
    """
    Create tree of page sections from given URL so it can be written to the database.
    """

    def __init__(self) -> None:
        self.text_analyzer = TextAnalyzer()
        self.summary_of_sections_so_far: str = ""

    def fetch(self, url: str) -> PageSection:
        """
        Fetch root page section from given page URL.
        """
        html_page = ""
        try:
            html_page = fetch_html_page(url=url)
        except Exception as e:
            raise ValueError(
                f"Failed to fetch HTML page {url} for indexing with error: {e}")

        root_section: HTMLSection = None
        try:
            root_section = parse_html(
                html_page=html_page, page_url=url)
        except Exception as e:
            raise ValueError(
                f"Failed to parse HTML page {url} during indexing with error: {e}")

        if not root_section.is_root_section():
            raise ValueError(f"Expected root section, got {root_section}")

        root_page_section = PageSection(is_root=True)
        for child_section in root_section.child_sections:
            page_section = self._generate_metadata(child_section)
            root_page_section.child_sections.append(page_section)

        root_page_section = PageSectionManager._populate_all_proper_nouns_in_each_section(
            root_page_section)

        return root_page_section

    def _generate_metadata(self, section: HTMLSection) -> PageSection:
        """
        Recursively traverses sections and generates summary, embedding and important entities for each section.
        Returns associated page section at the same level as given input HTMLSection.
        """
        # Compute detailed summary using current section and summary of sections so far.
        detailed_summary: str = ""
        text_so_far: str = ""
        if len(self.summary_of_sections_so_far) == 0:
            detailed_summary = self.text_analyzer.generate_detailed_summary(
                section.text)
            text_so_far = section.text
        else:
            detailed_summary = self.text_analyzer.generate_detailed_summary_with_context(
                text=section.text, preceding_text=self.summary_of_sections_so_far)
            text_so_far = "\n\n".join(
                [self.summary_of_sections_so_far, section.text])

        # Compute new concise summary of sections so far.
        # Concise so that detailed summary of subsequent sections doesn't exceed token limit.
        self.summary_of_sections_so_far = self.text_analyzer.generate_concise_summary(
            text_so_far)

        # Compute embedding of detailed summary.
        summary_vector_embedding: List[float] = self.text_analyzer.generate_vector_embedding(
            detailed_summary)

        # Computer proper nouns in section text.
        proper_nouns_in_section: List[str] = self.text_analyzer.generate_proper_nouns(
            section.text)

        # TODO: We may have to transform pronouns to lowercase, capitalize first letter, plurals (LD=1), stemming.
        # This can probably be done in indexing time.

        # Page section for given HTML section.
        page_section = PageSection(text=section.text, prev_sections_context=self.summary_of_sections_so_far, summary=detailed_summary,
                                   summary_vector_embedding=summary_vector_embedding, proper_nouns_in_section=proper_nouns_in_section)

        for child_section in section.child_sections:
            child_page_section = self._generate_metadata(child_section)

            # Add children from traversal to the tree.
            page_section.child_sections.append(child_page_section)

        return page_section

    @staticmethod
    def _populate_all_proper_nouns_in_each_section(root_page_section: PageSection):
        """
        Aggregate proper nouns from each section and then write it back to each section.
        This is similar to denormalization to ensure during search we can use this field
        as filter in the aggregation pipeline. Returns the same root section as result.
        """
        assert root_page_section.is_root, f"Expected root page section, got {root_page_section}"

        q = Queue()
        for child_section in root_page_section.child_sections:
            q.put(child_section)

        # Compute all proper nouns.
        all_proper_nouns_set = set()
        while not q.empty():
            section: PageSection = q.get()
            all_proper_nouns_set.update(section.proper_nouns_in_section)

            for child_section in section.child_sections:
                q.put(child_section)

        if len(all_proper_nouns_set) == 0:
            return root_page_section

        # Populate all proper nouns in each section.
        for child_section in root_page_section.child_sections:
            q.put(child_section)

        all_proper_nouns_list: List[str] = list(all_proper_nouns_set)
        while not q.empty():
            section: PageSection = q.get()
            section.proper_nouns_in_doc = all_proper_nouns_list

            for child_section in section.child_sections:
                q.put(child_section)

        return root_page_section


if __name__ == "__main__":
    section_manager = PageSectionManager()

    # url = 'https://support.atlassian.com/jira-software-cloud/docs/navigate-to-your-work/'
    url = 'https://flask.palletsprojects.com/en/3.0.x/extensions/'
    section_manager.fetch(url)
