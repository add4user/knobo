from userport.text_analyzer import TextAnalyzer
from userport.slack_models import (
    SlackSection,
    FindAndUpateSlackSectionRequest,
    FindSlackSectionRequest,
    UpdateSlackSectionRequest
)
from userport.utils import get_slack_web_client, get_hostname_url, create_documentation_url
from pydantic import BaseModel
import userport.db
from typing import List, Optional
import logging
import json
from celery import shared_task, chord


class SectionInfo(BaseModel):
    """
    Container for information per ordered
    section that is required for final update.
    """
    # Combined text (heading + body) in Markdown format.
    section_text: str
    # Current nouns in given section.
    nouns_in_section: List[str]
    # Find and update request for this section.
    fnu_request: FindAndUpateSlackSectionRequest


class SlackIndexingInfo(BaseModel):
    """
    Container for information that is passed
    acorss tasks in the slack page indexing workflow.
    """
    # ID of user who initiated the request.
    user_id: str
    # Whether request was for section creation or edit.
    creation: bool
    # Upload URL for the section
    upload_url: str
    # Current index of ordered sections list
    # that is being processed.
    current_idx: int
    # List of ordered section info.
    ordered_section_info_list: List[SectionInfo]
    # Summary of sections until (not including) current index.
    # Used to update FNU request for current sections's prev context.
    summary_of_sections_so_far: str


class SummaryAndEmbeddingResult(BaseModel):
    """
    Container class for computed section summary and its
    vector embedding.
    """
    section_summary: str
    summary_vector_embedding: List[float]


class NounsInSectionResult(BaseModel):
    """
    Container class for computed nouns in section.
    """
    nouns_in_section: List[str]


class SlackPageIndexerAsync:
    """
    Class to index page and associated sections and update them in the database.
    Assumes that Sections already exist associated with given page.

    We start indexing from the given section that was added or edited to all sections below.
    Since a section only affects summaries of subsequent sections and not previous ones.

    This class tries to parallelize as many API calls as possible to reduce indexing latency.
    """

    @staticmethod
    def run_from_section_async(section_id: str, user_id: str, creation: bool):
        """
        Run indexing from given section to all sections below it in the same page.

        We do this because the context can change for subsequent sections because of
        change in the given section.

        This method is async so do not rely on waiting for its completion at the callsite.
        """
        SlackPageIndexerAsync.notify_user_indexing_started(
            user_id=user_id, creation=creation)

        start_section: SlackSection = userport.db.get_slack_section(
            id=section_id)
        upload_url: str = create_documentation_url(
            host_name=get_hostname_url(),
            team_domain=start_section.team_domain,
            page_html_id=start_section.page_html_section_id,
            section_html_id=start_section.html_section_id
        )

        ordered_sections_in_page: List[SlackSection] = userport.db.get_ordered_slack_sections_in_page(
            team_domain=start_section.team_domain, page_html_section_id=start_section.page_html_section_id)

        start_index = 0
        while start_index < len(ordered_sections_in_page) and ordered_sections_in_page[start_index].id != start_section.id:
            # Keep moving forward.
            start_index += 1
        if start_index == len(ordered_sections_in_page):
            raise ValueError(
                f"Failed to find section: {str(start_section.id)} in page: {start_section.page_id}")

        logging.info(f"Start index: {start_index}")

        # Populate metadata for each section that needs to be updated.
        summary_of_sections_so_far = SlackPageIndexerAsync._initial_summary_of_sections(
            start_index=start_index, all_ordered_sections_in_page=ordered_sections_in_page)

        # Populate indexing info instance.
        ordered_section_info_list = []
        for section in ordered_sections_in_page:
            fnu_request = FindAndUpateSlackSectionRequest(
                find_request=FindSlackSectionRequest(id=section.id),
                # The nouns in doc is guaranteed to be populated for all sections in the workflow.
                # To start, we set the value as empty list but will update it at the end.
                update_request=UpdateSlackSectionRequest(
                    proper_nouns_in_doc=[])
            )
            # Nouns in section attribute will be update in the workflow for all sections that are updated.
            section_info = SectionInfo(nouns_in_section=section.proper_nouns_in_section, section_text=SlackPageIndexerAsync._get_combined_markdown_text(
                section), fnu_request=fnu_request)
            ordered_section_info_list.append(section_info)
        indexing_info = SlackIndexingInfo(user_id=user_id, current_idx=start_index, creation=creation, upload_url=upload_url,
                                          ordered_section_info_list=ordered_section_info_list, summary_of_sections_so_far=summary_of_sections_so_far)

        # Start workflow.
        SlackPageIndexerAsync._compute_metadata_in_section.delay(
            indexing_info.model_dump_json())

    @shared_task
    def _compute_metadata_in_section(indexing_info_json: str):
        """
        Compute metadata like summary, nouns, embedding etc. for given section.
        """
        indexing_info = SlackIndexingInfo(**json.loads(indexing_info_json))
        current_idx = indexing_info.current_idx
        current_section_info = indexing_info.ordered_section_info_list[current_idx]

        summary_of_sections_so_far: str = indexing_info.summary_of_sections_so_far
        section_text: str = current_section_info.section_text

        # TODO: We may have to transform pronouns to lowercase, capitalize first letter, plurals (LD=1), stemming.
        # as extra steps depending on accuracy of results.
        header = [
            SlackPageIndexerAsync._gen_section_summary_and_embedding.s(
                section_text=section_text, summary_of_sections_so_far=summary_of_sections_so_far),
            SlackPageIndexerAsync._gen_nouns_in_section.s(
                section_text=section_text),
            SlackPageIndexerAsync._gen_summary_of_page_so_far.s(
                section_text=section_text, summary_of_sections_so_far=summary_of_sections_so_far),
        ]

        callback = SlackPageIndexerAsync._process_metadata_in_section.s(
            indexing_info_json=indexing_info.model_dump_json())

        # Invoke chord.
        chord(header)(callback)

    @shared_task
    def _process_metadata_in_section(computed_results: List, indexing_info_json: str):
        """
        Process metadata computed previously and recursively call next computation if needed.
        """
        summary_and_embedding_result = SummaryAndEmbeddingResult(
            **json.loads(computed_results[0]))
        nouns_in_section_result = NounsInSectionResult(
            **json.loads(computed_results[1]))
        section_summary: str = summary_and_embedding_result.section_summary
        summary_vector_embedding: List[float] = summary_and_embedding_result.summary_vector_embedding
        nouns_in_section: List[str] = nouns_in_section_result.nouns_in_section
        next_summary_of_sections_so_far: str = computed_results[2]
        indexing_info = SlackIndexingInfo(**json.loads(indexing_info_json))

        current_idx = indexing_info.current_idx

        # Update current FNU request.
        current_section_info = indexing_info.ordered_section_info_list[current_idx]
        update_request: UpdateSlackSectionRequest = current_section_info.fnu_request.update_request
        update_request.summary = section_summary
        update_request.summary_vector_embedding = summary_vector_embedding
        update_request.proper_nouns_in_section = nouns_in_section
        update_request.prev_sections_context = indexing_info.summary_of_sections_so_far
        # Update nouns in section in current section info since this will be used later
        # to compute nouns in doc.
        current_section_info.nouns_in_section = nouns_in_section

        logging.info(
            f"Completed processing for section index: {current_idx} with text: {current_section_info.section_text[:5]}")

        if current_idx + 1 == len(indexing_info.ordered_section_info_list):
            # We are at the end of list, aggregage results.
            SlackPageIndexerAsync._complete_processing.delay(
                indexing_info.model_dump_json())
        else:
            # Update current index and summary of sections so far.
            indexing_info.current_idx = current_idx + 1
            indexing_info.summary_of_sections_so_far = next_summary_of_sections_so_far

            # Compute metadata for the next section.
            SlackPageIndexerAsync._compute_metadata_in_section.delay(
                indexing_info.model_dump_json())

    @shared_task
    def _complete_processing(indexing_info_json: str):
        """
        Complete processing and write updates to database.
        """
        indexing_info = SlackIndexingInfo(**json.loads(indexing_info_json))

        # Update nouns in doc.
        nouns_in_doc_set = set()
        for section_info in indexing_info.ordered_section_info_list:
            nouns_in_doc_set.update(section_info.nouns_in_section)

        # Update nouns in doc in FNU requests.
        nouns_in_doc: List[str] = list(nouns_in_doc_set)
        fnu_requests_list: List[FindAndUpateSlackSectionRequest] = []
        for section_info in indexing_info.ordered_section_info_list:
            section_info.fnu_request.update_request.proper_nouns_in_doc = nouns_in_doc
            fnu_requests_list.append(section_info.fnu_request)

        # Write all updates to database.
        userport.db.update_slack_sections(
            find_and_update_requests=fnu_requests_list)

        # Notify user that indexing is complete.
        SlackPageIndexerAsync.notify_user_indexing_complete(
            user_id=indexing_info.user_id, creation=indexing_info.creation, upload_url=indexing_info.upload_url)
        logging.info(f"Indexing complete")

    @shared_task
    def _gen_section_summary_and_embedding(section_text: str, summary_of_sections_so_far: str) -> str:
        """
        Generates summary of current section text (using summary of sections so far) and also
        the embedding of the summary and returns both as JSON string.
        """
        text_analyzer = TextAnalyzer()

        # Generate summary.
        section_summary = ""
        if summary_of_sections_so_far == "":
            section_summary = text_analyzer.generate_detailed_summary(
                text=section_text, markdown=True)
        else:
            section_summary = text_analyzer.generate_detailed_summary_with_context(
                text=section_text, preceding_text=summary_of_sections_so_far, markdown=True)

        # Generate embedding.
        embedding = text_analyzer.generate_vector_embedding(section_summary)

        result = SummaryAndEmbeddingResult(
            section_summary=section_summary, summary_vector_embedding=embedding)
        return result.model_dump_json()

    @shared_task
    def _gen_nouns_in_section(section_text: str) -> str:
        """
        Generates all nouns in given section text and returns JSON string.
        """
        text_analyzer = TextAnalyzer()
        nouns_in_section: List[str] = text_analyzer.generate_all_nouns(
            text=section_text)
        result = NounsInSectionResult(nouns_in_section=nouns_in_section)
        return result.model_dump_json()

    @shared_task
    def _gen_summary_of_page_so_far(section_text: str, summary_of_sections_so_far: str) -> str:
        """
        Generates new summary of sections using current summary of sections.

        This will be used as preceding text in the next section in the chain.
        We want to make a concise summary so that detailed summary of the next section doesn't exceed token limit.
        """
        page_text_seen_so_far: str = ""
        if summary_of_sections_so_far == "":
            page_text_seen_so_far = section_text
        else:
            page_text_seen_so_far = SlackPageIndexerAsync._page_text_so_far(
                summary_of_sections_so_far=summary_of_sections_so_far, section_text=section_text)

        text_analyzer = TextAnalyzer()
        return text_analyzer.generate_concise_summary(text=page_text_seen_so_far, markdown=True)

    @staticmethod
    def _initial_summary_of_sections(start_index: int, all_ordered_sections_in_page: List[SlackSection]) -> str:
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
                    page_text_seen_so_far: str = SlackPageIndexerAsync._page_text_so_far(
                        summary_of_sections_so_far=last_section.prev_sections_context, section_text=SlackPageIndexerAsync._get_combined_markdown_text(last_section))
                    text_analyzer = TextAnalyzer()
                    summary_of_sections_so_far = text_analyzer.generate_concise_summary(
                        text=page_text_seen_so_far, markdown=True)
        return summary_of_sections_so_far

    @staticmethod
    def _page_text_so_far(summary_of_sections_so_far: str, section_text: str) -> str:
        """
        Helper to return page text so far from summary of sections and current section text.
        """
        return f"{summary_of_sections_so_far}\n\n{section_text}"

    @staticmethod
    def _get_combined_markdown_text(section: SlackSection) -> str:
        """
        Returns markdown text combining heading and text within a section.
        """
        return f"{section.heading}\n\n{section.text}"

    @staticmethod
    def notify_user_indexing_started(user_id: str, creation: bool):
        """
        Notify user via Slack that indexing has started. Message will be posted
        to user's DM with Knobo.
        """
        web_client = get_slack_web_client()
        if creation:
            # User has created section.
            web_client.chat_postEphemeral(channel=user_id, user=user_id,
                                          text="Section creation is in progress! I will ping you once it's done!")
        else:
            # User has edited section.
            web_client.chat_postEphemeral(channel=user_id, user=user_id,
                                          text=f"Section Edit in progress! I will ping you once it's done!")

    @staticmethod
    def notify_user_indexing_complete(user_id: str, creation: bool, upload_url: str):
        """
        Notify user via Slack that indexing has completed. Message will be posted
        to user's DM with Knobo.
        """
        web_client = get_slack_web_client()
        if creation:
            web_client.chat_postEphemeral(channel=user_id, user=user_id,
                                          text=f"Section creation complete! Available at {upload_url}")
        else:
            web_client.chat_postEphemeral(channel=user_id, user=user_id,
                                          text=f"Section Edit complete! Updated section at: {upload_url}")
