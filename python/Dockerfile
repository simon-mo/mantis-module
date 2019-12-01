FROM python:3.6

# Install binaries utility for debugging need
RUN apt update
RUN apt install -y vim redis jq

# Install python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the debug trace 4min big-spike
COPY traces/debug.npy .

# Install the mantis python package
COPY . .
RUN pip install -e .

# Test installation
RUN mantis --help
