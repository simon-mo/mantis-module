from mantis.models.sleep import Sleeper, BusySleeper
from mantis.models.transformer import SentimentAnalysis
from mantis.models.squeezenet import Squeezenet

catalogs = {
    "sleep": Sleeper,
    "busy-sleep": BusySleeper,
    "vision": Squeezenet,
    "nlp": SentimentAnalysis,
}
