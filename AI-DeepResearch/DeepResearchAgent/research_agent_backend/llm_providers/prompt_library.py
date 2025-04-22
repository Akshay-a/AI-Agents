import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Basic prompt for synthesis - can be greatly improved
SYNTHESIS_PROMPT_TEMPLATE = """
You are an expert research assistant. Your goal is to synthesize information from multiple sources into a coherent and concise summary relevant to the main topic.

**Main Research Topic:**
{topic}

**Sources:**
{sources_text}

**Instructions:**
1. Carefully read the provided text from all sources.
2. Identify the key findings, arguments, data points, and conclusions relevant to the main research topic.
3. Synthesize this information into a well-structured summary.
4. Focus on accuracy and objectivity. Do not add information not present in the sources.
5. Ensure the summary is concise and easy to understand.
6. Start the summary directly, without introductory phrases like "Here is a summary...".

**Synthesized Summary:**
"""

MAP_PROMPT_TEMPLATE = """
You are an expert analyst. Your task is to extract key information from the provided text relevant to a specific research topic. Focus ONLY on the information presented in the text.

**Main Research Topic:**
{topic}

**Text Segment from Source URL ({url}):**

{text_segment}


**Instructions:**
1. Carefully read the text segment provided above.
2. Identify and extract ONLY the key facts, figures, arguments, findings, and conclusions that are directly relevant to the **Main Research Topic: "{topic}"**.
3. Present the extracted information concisely, using bullet points or short sentences.
4. **Crucially, maintain the context of the source:** Ensure the extracted points accurately reflect the information from this specific text segment.
5. Do NOT add any information not present in the text segment.
6. Do NOT add introductory or concluding remarks like "Based on the text..." or "In conclusion...".
7. If the text segment is irrelevant to the main topic, output the single word: "IRRELEVANT".

**Extracted Key Information Relevant to "{topic}":**
"""

REDUCE_PROMPT_TEMPLATE = """
You are an expert research synthesizer. Your task is to synthesize extracted information from multiple sources into a single, coherent, and well-structured research report relevant to the main topic.

**Main Research Topic:**
{topic}

**Extracted Information from Sources:**
{extracted_data}

**Instructions:**
1. Carefully review the extracted information provided above, noting the source URL for each piece of information.
2. Synthesize these pieces of information into a comprehensive and well-structured research report answering the **Main Research Topic: "{topic}"**.
3. Structure the report using Markdown formatting:
    - Start with a title: `# Research Report: {topic}`
    - Include an `## Introduction / Overview` section summarizing the topic and key findings.
    - Organize the main findings into logical sections using `## Key Theme / Aspect` headings (e.g., `## Core Concepts`, `## Historical Development`, `## Current Challenges`, `## Future Outlook`). Group related points under appropriate themes.
    - **Where possible, cite the source URL in parentheses after presenting a specific piece of information**, like `(Source: {url})`. Try to consolidate citations if multiple points come from the same source within a paragraph.
    - Optionally include a `## Contradictions / Nuances` section if conflicting information or important subtleties were found in the sources.
    - Conclude with a `## Conclusion` section summarizing the overall synthesized understanding.
    - Finally, include a `## Sources Used` section listing all the unique source URLs referenced in the report.
4. Ensure the report flows logically and is easy to read.
5. Base the report **strictly** on the provided extracted information. Do not add external knowledge or information not present in the extracts.
6. Be objective and maintain a neutral tone.

**Final Synthesized Research Report (Markdown Format):**
"""

FINAL_SYNTHESIS_PROMPT_TEMPLATE = """
You are an expert research analyst and writer. Your task is to synthesize information from the provided sources (which may include full texts and summaries) into a single, coherent, comprehensive, and well-structured research report relevant to the main topic.

**Main Research Topic:**
{topic}

**Provided Information (Mixture of Full Texts and Summaries):**
{synthesis_input_text}

**Instructions:**
1. Carefully review all the provided information. Prioritize details from "Source (Full Text)" sections where available, using "Source (Summary)" sections to supplement understanding or cover sources that couldn't be included in full.
2. Synthesize this information into a high-quality research report answering the **Main Research Topic: "{topic}"**.
3. Structure the report using Markdown formatting:
    - Title: `# Research Report: {topic}`
    - `## Executive Summary`: A brief (2-3 paragraph) overview of the key findings and conclusions.
    - `## Introduction`: Briefly introduce the topic and the scope of the report based on the provided sources.
    - `## Key Findings / Thematic Sections`: Organize the main findings into logical sections using `## Appropriate Theme Heading` (e.g., `## Core Concepts`, `## Applications`, `## Challenges`, `## Future Directions`). Synthesize information from across sources for each theme.
    - `## Contradictions / Nuances` (Optional but Recommended): If significant disagreements or important subtleties exist across sources, discuss them here.
    - `## Conclusion`: Summarize the main points and provide a concluding thought based *only* on the synthesized information.
    - `## Sources Used`: List all unique source URLs referenced in the report (extract URLs provided in the input text like `Source: http://...`).
4. **Cite sources accurately within the text** using `(Source: {url})` immediately after the information derived from that source. Consolidate citations where appropriate within a paragraph.
5. Ensure the report flows logically, is well-written, objective, and comprehensive based *only* on the provided text and summaries. Do not add external knowledge.
6. Be thorough and detailed in the "Key Findings" sections.

**Final Synthesized Research Report (Markdown Format):**
"""

DOCUMENT_SUMMARY_PROMPT_TEMPLATE = """
You are an expert summarizer. Your task is to read the following document text and extract a concise summary of the key information **strictly relevant** to the main research topic provided.

**Main Research Topic:**
{topic}

**Document Text from Source URL ({url}):**

{document_text}


**Instructions:**
1. Focus *only* on information directly related to the **Main Research Topic: "{topic}"**.
2. Extract the most important facts, findings, arguments, or conclusions presented in the text regarding the topic.
3. Produce a concise, factual summary. Use bullet points if appropriate for clarity.
4. Do NOT add information not present in the document text.
5. Do NOT include introductory phrases like "This document discusses...". Start the summary directly.
6. If the document contains NO information relevant to the main topic, output the single word: "IRRELEVANT".

**Concise Summary Relevant to "{topic}":**
"""

# --- Add formatting functions ---
def format_final_synthesis_prompt(topic: str, synthesis_input_text: str) -> str:
    """Formats the prompt for the final synthesis stage."""
    # Basic formatting, ensure topic is included in title etc.
    prompt = FINAL_SYNTHESIS_PROMPT_TEMPLATE.replace("{topic}", topic)
    prompt = prompt.replace("{synthesis_input_text}", synthesis_input_text)
    return prompt

def format_document_summary_prompt(topic: str, document_text: str, url: str) -> str:
    """Formats the prompt for summarizing a single overflow document."""
    return DOCUMENT_SUMMARY_PROMPT_TEMPLATE.format(topic=topic, document_text=document_text, url=url)

def format_map_prompt(topic: str, text_segment: str, url: str) -> str:
    """Formats the prompt for the Map step."""
    return MAP_PROMPT_TEMPLATE.format(topic=topic, text_segment=text_segment, url=url)

def format_reduce_prompt(topic: str, mapped_insights: List[Dict[str, Any]], max_tokens: int = 150000) -> str:
    """
    Formats the prompt for the Reduce step, combining insights from the Map step.

    Args:
        topic (str): The main research topic.
        mapped_insights (List[Dict[str, Any]]): List of dictionaries, each containing
                                                'url' and 'extracted_info'.
        max_tokens (int): Approximate max tokens for the combined insights text.

    Returns:
        str: The formatted prompt for the final synthesis.
    """
    extracted_data_str = ""
    current_length = 0
    # Rough estimate: 4 chars per token (adjust as needed)
    # Leave ample room for the rest of the prompt template itself
    max_chars = max_tokens * 3

    included_sources = 0
    for insight in mapped_insights:
        url = insight.get('url', 'Unknown Source')
        info = insight.get('extracted_info', '').strip()

        # Skip if marked irrelevant or empty
        if not info or info.upper() == "IRRELEVANT":
            continue

        insight_header = f"\n--- Information from Source: {url} ---\n"
        insight_content = info

        if current_length + len(insight_header) + len(insight_content) > max_chars:
            logger.warning(f"Truncating mapped insight from {url} to fit Reduce prompt limit.")
            remaining_chars = max_chars - current_length - len(insight_header) - 10
            if remaining_chars > 50:
                insight_content = insight_content[:remaining_chars] + "..."
            else:
                logger.warning(f"Skipping mapped insight from {url} entirely due to Reduce prompt limit.")
                continue # Skip this insight

        extracted_data_str += insight_header + insight_content + "\n"
        current_length += len(insight_header) + len(insight_content) + 1
        included_sources += 1
        if current_length >= max_chars:
            logger.warning("Reached approximate maximum character limit for Reduce prompt insights.")
            break

    if not extracted_data_str:
        extracted_data_str = "No relevant information was extracted from the provided sources."

    logger.info(f"Formatted Reduce prompt. Included insights from {included_sources} map results. Approx length: {len(extracted_data_str)}")
    return REDUCE_PROMPT_TEMPLATE.format(topic=topic, extracted_data=extracted_data_str)


def format_synthesis_prompt(topic: str, documents: List[Dict[str, Any]], max_tokens: int = 100000) -> str:
    """
    Formats the prompt for the synthesis task, trying to fit within token limits.

    Args:
        topic (str): The main research topic.
        documents (List[Dict[str, Any]]): List of documents, each expected to have
                                          'url' and 'extracted_text'.
        max_tokens (int): Approximate maximum tokens allowed for the sources text.
                          (Note: Token counting is best done by the provider later)

    Returns:
        str: The formatted prompt ready for the LLM.
    """
    sources_text = ""
    current_length = 0
    max_chars = max_tokens * 4 # Rough estimate: 4 chars per token

    for i, doc in enumerate(documents):
        url = doc.get('url', f'Source {i+1}')
        text = doc.get('extracted_text', '')
        if not text:
            continue

        source_header = f"\n--- Source {i+1}: {url} ---\n"
        source_content = text

        # Basic length check to avoid excessively long prompts
        if current_length + len(source_header) + len(source_content) > max_chars:
            # Try truncating the content
            remaining_chars = max_chars - current_length - len(source_header) - 10 # Add buffer
            if remaining_chars > 100: # Only add if we can fit a reasonable chunk
                source_content = source_content[:remaining_chars] + "..."
                logger.warning(f"Truncating content from source {url} to fit approximate token limit.")
            else:
                logger.warning(f"Skipping source {url} due to approximate token limit.")
                continue # Skip this document entirely if it won't fit

        sources_text += source_header + source_content
        current_length += len(source_header) + len(source_content)
        if current_length >= max_chars:
            logger.warning("Reached approximate maximum character limit for sources.")
            break # Stop adding documents

    if not sources_text:
        sources_text = "No sources provided or text could not be extracted."

    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(topic=topic, sources_text=sources_text)
    logger.info(f"Formatted synthesis prompt. Topic: '{topic}'. Included {i+1 if sources_text else 0} sources. Approx length: {len(prompt)}")
    return prompt

# Add more prompts here later (e.g., for planning, fact-checking, etc.)