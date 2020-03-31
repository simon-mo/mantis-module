from transformers import pipeline


class SentimentAnalysis:
    def __init__(self):
        self.nlp = pipeline("sentiment-analysis")

    def __call__(self, payload):
        # 51.7 ms ± 104 µs per loop (mean ± std. dev. of 7 runs, 10 loops each)
        return self.nlp(payload)

    @staticmethod
    def generate_workload():
        return "Don't worry be happy"
