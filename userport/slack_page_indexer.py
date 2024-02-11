from userport.text_analyzer import TextAnalyzer
from userport.slack_models import (
    SlackSection,
    FindAndUpateSlackSectionRequest,
    FindSlackSectionRequest,
    UpdateSlackSectionRequest
)
from bson.objectid import ObjectId
import userport.db
from typing import List


class SlackPageIndexer:
    """
    Class to index page and associated sections and update them in the database.

    TODO: Right now we are re-indexing all the sections in a given page. This can be made
    more efficient by just indexing from the given section that was added or edited to all sections below.
    Since a section only affects summaries of subsequent sections and not previous ones.
    """

    def __init__(self) -> None:
        self.text_analyzer = TextAnalyzer(debug=True)
        self.summary_of_sections_so_far: str = ""
        self.all_sections_in_page: List[SlackSection] = []

    def run(self, page_id: str):
        """
        Index all sections in given page and writes them to database. 
        """
        page_section: SlackSection = userport.db.get_slack_section(id=page_id)
        self._generate_metadata(section=page_section)
        self._populate_all_proper_nouns_in_each_section()
        self._write_all_sections_to_db()

    def _generate_metadata(self, section: SlackSection):
        """
        Generate metadata for given Slack section.
        """
        self.all_sections_in_page.append(section)

        # Compute detailed summary using current section and summary of sections so far.
        detailed_summary: str = ""
        page_text_seen_so_far: str = ""

        section_text = self._get_combined_markdown_text(section)
        if len(self.summary_of_sections_so_far) == 0:
            detailed_summary = self.text_analyzer.generate_detailed_summary(
                text=section_text, markdown=True)
            page_text_seen_so_far = section_text
        else:
            detailed_summary = self.text_analyzer.generate_detailed_summary_with_context(
                text=section_text, preceding_text=self.summary_of_sections_so_far, markdown=True)
            page_text_seen_so_far = f"{self.summary_of_sections_so_far}\n\n{section.text}"

        # Compute embedding of the detailed summary of current section.
        summary_vector_embedding: List[float] = self.text_analyzer.generate_vector_embedding(
            detailed_summary)

        # Computer proper nouns in section text.
        proper_nouns_in_section: List[str] = self.text_analyzer.generate_proper_nouns(
            text=section_text, markdown=True)

        # TODO: We may have to transform pronouns to lowercase, capitalize first letter, plurals (LD=1), stemming.
        # This can probably be done in indexing time.

        # Populate metadata attributes in section.
        section.summary = detailed_summary
        section.prev_sections_context = self.summary_of_sections_so_far
        section.summary_vector_embedding = summary_vector_embedding
        section.proper_nouns_in_section = proper_nouns_in_section

        # Update summary of sections so far. This will be used as preceding text in the next section in the chain.
        # We want to make a concise summary so that detailed summary of the next section doesn't exceed token limit.
        self.summary_of_sections_so_far = self.text_analyzer.generate_concise_summary(
            text=page_text_seen_so_far, markdown=True)

        # Traverse children.
        for child_section_id in section.child_section_ids:
            child_section: SlackSection = userport.db.get_slack_section(
                id=child_section_id)
            self._generate_metadata(child_section)

    def _get_combined_markdown_text(self, section: SlackSection) -> str:
        """
        Returns markdown text combining heading and text within a section.
        """
        return f"{section.heading}\n\n{section.text}"

    def _populate_all_proper_nouns_in_each_section(self):
        """
        Aggregate proper nouns from each section and then write it back to each section.
        This is similar to denormalization to ensure during search we can use this field
        as filter in the aggregation pipeline.
        """
        # Compute all proper nouns.
        all_proper_nouns_set = set()
        for section in self.all_sections_in_page:
            all_proper_nouns_set.update(section.proper_nouns_in_section)

        if len(all_proper_nouns_set) == 0:
            # No need to do anything.
            return

        # Populate all proper nouns in each section.
        all_proper_nouns_list: List[str] = list(all_proper_nouns_set)
        for section in self.all_sections_in_page:
            section.proper_nouns_in_doc = all_proper_nouns_list

    def _write_all_sections_to_db(self):
        """
        Write all sections to database with updates to metadata.
        """
        find_and_update_requests: List[FindAndUpateSlackSectionRequest] = []
        for section in self.all_sections_in_page:
            find_request = FindSlackSectionRequest(id=ObjectId(section.id))
            update_request = UpdateSlackSectionRequest(
                summary=section.summary,
                prev_sections_context=section.prev_sections_context,
                summary_vector_embedding=section.summary_vector_embedding,
                proper_nouns_in_section=section.proper_nouns_in_section,
                proper_nouns_in_doc=section.proper_nouns_in_doc
            )
            find_and_update_requests.append(
                FindAndUpateSlackSectionRequest(
                    find_request=find_request,
                    update_request=update_request
                )
            )
        userport.db.update_slack_sections(find_and_update_requests)
