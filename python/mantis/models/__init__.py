from mantis.models.sleep import Sleeper
from mantis.models.transformer import SentimentAnalysis
from mantis.models.squeezenet import Squeezenet

catalogs = {
    "sleep": Sleeper,
    "vision": Squeezenet,
    "nlp": SentimentAnalysis,
}
