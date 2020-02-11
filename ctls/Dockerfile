FROM python:3.6

# Install binaries utility for debugging need
RUN apt update
RUN apt install -y vim redis jq

# Install kubectl
RUN apt-get install -y apt-transport-https
RUN curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
RUN echo "deb https://apt.kubernetes.io/ kubernetes-xenial main" | tee -a /etc/apt/sources.list.d/kubernetes.list
RUN apt-get update
RUN apt-get install -y kubectl

# Install python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install the mantis python package
COPY . .
RUN pip install -e .

CMD ["python", "mantis_ctl/runner.py"]
