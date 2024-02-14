from userport.text_analyzer import TextAnalyzer
from userport.slack_models import (
    SlackSection,
    FindAndUpateSlackSectionRequest,
    FindSlackSectionRequest,
    UpdateSlackSectionRequest
)
from bson.objectid import ObjectId
import userport.db
from typing import List, Dict
import logging


class SlackPageIndexer:
    """
    Class to index page and associated sections and update them in the database.
    Assumes that Sections already exist associated with given page.

    We start indexing from the given section that was added or edited to all sections below.
    Since a section only affects summaries of subsequent sections and not previous ones.
    """

    def __init__(self) -> None:
        self.text_analyzer = TextAnalyzer(debug=False)

    def run_from_section(self, section_id: str):
        """
        Run indexing from given section to all sections below it in the same page.

        We do this because the context can change for subsequent sections because of
        change in the given section.
        """
        start_section: SlackSection = userport.db.get_slack_section(
            id=section_id)
        all_ordered_sections_in_page: List[SlackSection] = userport.db.get_ordered_slack_sections_in_page(
            team_domain=start_section.team_domain, page_html_section_id=start_section.page_html_section_id)

        start_index = 0
        while start_index < len(all_ordered_sections_in_page) and all_ordered_sections_in_page[start_index].id != start_section.id:
            start_index += 1

        logging.info(f"Start index: {start_index}")

        if start_index == len(all_ordered_sections_in_page):
            raise ValueError(
                f"Failed to find section: {str(start_section.id)} in page: {start_section.page_id}")

        # Populate metadata for each section that needs to be updated.
        summary_of_sections_so_far = self._initial_summary_of_sections(
            start_index=start_index, all_ordered_sections_in_page=all_ordered_sections_in_page)
        all_nouns_set = set()
        find_and_update_requests_dict: Dict[str,
                                            FindAndUpateSlackSectionRequest] = {}
        for i in range(len(all_ordered_sections_in_page)):
            section = all_ordered_sections_in_page[i]
            if i < start_index:
                # Just add existing nouns to all sections.
                all_nouns_set.update(section.proper_nouns_in_section)
                continue

            summary_of_sections_so_far, all_nouns_in_section = self._populate_metadata_in_section(
                section=section, summary_of_sections_so_far=summary_of_sections_so_far)
            all_nouns_set.update(all_nouns_in_section)

            # Create update request for this section.
            find_request = FindSlackSectionRequest(id=section.id)
            update_request = UpdateSlackSectionRequest(
                summary=section.summary,
                prev_sections_context=section.prev_sections_context,
                summary_vector_embedding=section.summary_vector_embedding,
                proper_nouns_in_section=section.proper_nouns_in_section
            )
            find_and_update_request = FindAndUpateSlackSectionRequest(
                find_request=find_request, update_request=update_request)
            find_and_update_requests_dict[str(
                section.id)] = find_and_update_request

        # Populate all nouns for each section in the page including the ones that were before the start index.
        all_nouns_list: List[str] = list(all_nouns_set)
        for section in all_ordered_sections_in_page:
            section_id = str(section.id)
            if section_id not in find_and_update_requests_dict:
                find_and_update_requests_dict[section_id] = FindAndUpateSlackSectionRequest(
                    find_request=FindSlackSectionRequest(
                        id=ObjectId(section_id)),
                    update_request=UpdateSlackSectionRequest(
                        proper_nouns_in_doc=all_nouns_list)
                )
                logging.info(f"new nouns update for:  {section.heading}")
            else:
                find_and_update_requests_dict[section_id].update_request.proper_nouns_in_doc = all_nouns_list
                logging.info(f"existing nouns update for:  {section.heading}")

        # Write updates to database.
        find_and_update_requests_list: List[str] = list(
            find_and_update_requests_dict.values())
        userport.db.update_slack_sections(
            find_and_update_requests=find_and_update_requests_list)

    def _populate_metadata_in_section(self, section: SlackSection, summary_of_sections_so_far: str):
        """
        Populate metadata like summary, nouns, embedding etc. for given section and return the
        summary of all sections traversed so far and the nouns in the given section.
        """
        # Compute detailed summary using current section and summary of sections so far.
        detailed_summary: str = ""
        page_text_seen_so_far: str = ""

        section_text = self._get_combined_markdown_text(section)
        if summary_of_sections_so_far == "":
            detailed_summary = self.text_analyzer.generate_detailed_summary(
                text=section_text, markdown=True)
            page_text_seen_so_far = section_text
        else:
            detailed_summary = self.text_analyzer.generate_detailed_summary_with_context(
                text=section_text, preceding_text=summary_of_sections_so_far, markdown=True)
            page_text_seen_so_far = self._page_text_so_far(
                summary_of_sections_so_far=summary_of_sections_so_far, section_text=section_text)

        # Compute embedding of the detailed summary of current section.
        summary_vector_embedding: List[float] = self.text_analyzer.generate_vector_embedding(
            detailed_summary)

        # Computer proper nouns in section text.
        all_nouns_in_section: List[str] = self.text_analyzer.generate_all_nouns(
            text=section_text)

        # TODO: We may have to transform pronouns to lowercase, capitalize first letter, plurals (LD=1), stemming.
        # This can probably be done in indexing time.

        # Populate metadata attributes in section.
        section.summary = detailed_summary
        section.prev_sections_context = summary_of_sections_so_far
        section.summary_vector_embedding = summary_vector_embedding
        section.proper_nouns_in_section = all_nouns_in_section

        # Update summary of sections so far. This will be used as preceding text in the next section in the chain.
        # We want to make a concise summary so that detailed summary of the next section doesn't exceed token limit.
        summary_of_sections_so_far = self.text_analyzer.generate_concise_summary(
            text=page_text_seen_so_far, markdown=True)

        return summary_of_sections_so_far, all_nouns_in_section

    def _initial_summary_of_sections(self, start_index: int, all_ordered_sections_in_page: List[SlackSection]) -> str:
        """
        Helper to compute initial summary of section for the newly added
        or edited section. The logic is complex to account for both newly
        added and edited section.

        start_index denotes the section in  all_ordered_sections_in_page at which indexing will start.
        """
        summary_of_sections_so_far = ""
        if start_index > 0:
            summary_of_sections_so_far = all_ordered_sections_in_page[
                start_index].prev_sections_context
            if summary_of_sections_so_far == "":
                if start_index < len(all_ordered_sections_in_page) - 1:
                    # This section has been newly added, so use context from next section.
                    # The next section was the "previous" next section before this section
                    # was added.
                    summary_of_sections_so_far = all_ordered_sections_in_page[
                        start_index+1].prev_sections_context
                else:
                    # Since this is the last section, we compute the summary from last section again.
                    last_section = all_ordered_sections_in_page[-2]
                    page_text_seen_so_far: str = self._page_text_so_far(
                        summary_of_sections_so_far=last_section.prev_sections_context, section_text=self._get_combined_markdown_text(last_section))
                    summary_of_sections_so_far = self.text_analyzer.generate_concise_summary(
                        text=page_text_seen_so_far, markdown=True)
        return summary_of_sections_so_far

    def _page_text_so_far(self, summary_of_sections_so_far: str, section_text: str) -> str:
        """
        Helper to return page text so far from summary of sections and current section text.
        """
        return f"{summary_of_sections_so_far}\n\n{section_text}"

    def _get_combined_markdown_text(self, section: SlackSection) -> str:
        """
        Returns markdown text combining heading and text within a section.
        """
        return f"{section.heading}\n\n{section.text}"
