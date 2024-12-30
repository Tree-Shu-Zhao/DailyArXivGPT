RESEARCH_INTEREST_PROMPT = """1. Retrieval-Augmented Generation (RAG), expecially focuses on Multimodal RAG.
2. Multimodal Retrieval.
3. Long-Context."""

RELEVANCE_SCORE_PROMPT = """You have been asked to read a paper's title and abstract. Based on my research interests, you should rate this paper on a scale of 1-10, with a higher score indicating greater relevance. Additionally, please generate a 1-2 sentence summary for this paper explaining why it's relevant to my research interests. The output should be in a JSON format with the following structure:

Example:
1. {"Score": "an integer score out of 10", "Reasons": "1-2 sentence short reasonings"}

My research interests are: """ + "\n" + RESEARCH_INTEREST_PROMPT