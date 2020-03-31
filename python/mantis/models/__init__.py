from mantis.models.sleep import Sleeper
from mantis.models.transformer import SentimentAnalysis
from mantis.models.squeezenet import Squeezenet

catalogs = {
    "sleep": Sleeper,
    "vision": Squeezenet,
    "nlp": SentimentAnalysis,
}


def preload_models():
    from transformers import pipeline
    from torchvision.models import squeezenet1_1

    pipeine("sentiment-analysis")
    squeezenet1_1(pretrained=True)
