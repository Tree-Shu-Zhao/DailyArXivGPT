class Paper:
    def __init__(self, title, link, description):
        self.title = title
        self.link = link
        self.description = description
        self.relevance_score = None
        self.relevance_reasons = None
    