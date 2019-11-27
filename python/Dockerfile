FROM python:3.6

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY traces/debug.npy .

COPY . .
RUN pip install -e .

# Test installation
RUN mantis --help