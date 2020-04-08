FROM python:3.6

# Install binaries utility for debugging need
RUN apt update
RUN apt install -y vim redis jq

# Download models
RUN pip install torch==1.4.0+cpu torchvision==0.5.0+cpu -f https://download.pytorch.org/whl/torch_stable.html
RUN pip install transformers
COPY download_deps.py .
RUN python download_deps.py

# Install python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install the mantis python package
COPY . .
RUN pip install -e .

# Test installation
RUN mantis --help
