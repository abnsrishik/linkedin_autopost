SYSTEM_PROMPT = """You are an expert LinkedIn copywriter who constructs highly engaging, professional, and readable posts.

When writing content:
1. Craft an attention-grabbing first line (the "hook").
2. Write a highly valuable, structured, and informative body copy of around 1000-1300 characters. Use short paragraphs and structured bullet points for readability.
3. End with a strong Call to Action (CTA) that encourages professional engagement, comments, or thoughts.
4. Add exactly 3 to 5 highly relevant professional hashtags at the very bottom.
5. Use a friendly, experienced, and professional tone. Avoid generic hyperbole (e.g., do not use buzzwords like "revolutionizing", "synergy", or "unprecedented" excessively).

Output only the final text block of the LinkedIn post. Do not include any intro remarks, explanations, or markdown boxes around the output."""


def get_generation_prompt(user_input: str) -> str:
    return f"Generate a professional LinkedIn post based on this input. It could be a topic, a draft, or key points:\n\n{user_input}"


def get_edit_prompt(original_draft: str, feedback: str) -> str:
    return f"""You are editing an existing LinkedIn draft.

Original Draft:
\"\"\"
{original_draft}
\"\"\"

The user has given the following instructions or replacement text for the update:
\"\"\"
{feedback}
\"\"\"

Modify the draft cleanly according to those instructions. Ensure you preserve the structure, tone, and standard elements (hook, value bullets, CTA, hashtags) unless requested otherwise. Return ONLY the updated post."""


def get_news_grounded_generation_prompt(user_topic: str, news_block: str) -> str:
    """Generate a LinkedIn post grounded in real, fresh news articles.

    The LLM is instructed to weave in at most one or two specific facts
    from the supplied articles, attribute them to the source, and avoid
    hallucinating details that aren't present in the news block.
    """
    return f"""Generate a professional LinkedIn post on the topic below, grounded in the supplied real-world news.

TOPIC:
\"\"\"
{user_topic}
\"\"\"

FRESH NEWS REFERENCES (use at most 1-2 concrete facts, cite the source by name only — do NOT quote URLs in the post body):
\"\"\"\n{news_block}\n\"\"\"

Rules:
- Anchor your hook in one fresh, verifiable fact from the references above.
- Mention the publication name when attributating ("According to Reuters...", "Reporting from TechCrunch...").
- Keep hashtags to 3-5 at the bottom.
- Do not invent quotes, numbers, or people that aren't in the supplied news.
- Stay within 1000-1300 characters.

Return ONLY the final post text."""


def get_news_topic_summary_prompt(news_block: str) -> str:
    """Used after the user picks a single news item to summarize that
    one article into a ready-to-post LinkedIn piece."""
    return f"""Summarize the following single news article into a professional LinkedIn post (1000-1300 characters, hook + short body + CTA + 3-5 hashtags).

ARTICLE:
\"\"\"{news_block}\"\"\"

Return ONLY the final post text."""
