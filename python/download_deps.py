from transformers import pipeline
from torchvision.models import squeezenet1_1

pipeline("sentiment-analysis")
squeezenet1_1(pretrained=True)
