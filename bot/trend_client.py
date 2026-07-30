from bot.research.router import ResearchRouter


class TrendClient:
    def __init__(self, router=None, **_legacy_kwargs):
        self.router = router or ResearchRouter()

    def fetch_topics(self, limit=3, exclude_topics=None):
        topics = self.router.trending_topics(
            limit=limit,
            exclude_topics=exclude_topics,
        )
        return [self._topic_title(topic) for topic in topics]

    def fetch_topic_research(self, topic):
        return self.router.research(topic)

    def _topic_title(self, topic):
        if isinstance(topic, str):
            return topic
        if isinstance(topic, dict):
            return topic.get("title", "")
        return getattr(topic, "title", topic)
