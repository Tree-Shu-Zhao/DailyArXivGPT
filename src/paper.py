class Paper:
    def __init__(self, title, link, abstract, relevance_score=None, relevance_reasons=None, key_contributions=None):
        self.title = title
        self.link = link
        self.abstract = abstract
        self.relevance_score = relevance_score
        self.relevance_reasons = relevance_reasons
        self.key_contributions = key_contributions

    def to_dict(self):
        return {
            'title': self.title,
            'link': self.link,
            'abstract': self.abstract,
            'relevance_score': self.relevance_score,
            'relevance_reasons': self.relevance_reasons,
            'key_contributions': self.key_contributions
        }

    @classmethod
    def from_dict(cls, data):
        paper = cls(
            title=data['title'],
            link=data['link'],
            abstract=data['abstract'],
            relevance_score=data.get('relevance_score'),
            relevance_reasons=data.get('relevance_reasons'),
            key_contributions=data.get('key_contributions')
        )
        return paper

    def __str__(self):
        return f"{self.title}\n{self.link}\n{self.abstract}\nScore: {self.relevance_score}\nReasons: {self.relevance_reasons}\nKey Contributions: {self.key_contributions}"

    def __repr__(self):
        return self.__str__()
