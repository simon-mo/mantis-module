from transformers import pipeline
from torchvision.models import squeezenet1_1

_ = pipeline("sentiment-analysis")
_ = squeezenet1_1(pretrained=True)
