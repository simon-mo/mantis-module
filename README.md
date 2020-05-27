## Mantis Redis Module

This repository contains system artifact for the mantis experiment testbed.

- Use jsonnet to generate experiment sets, checkout the Makefile in `experiments` directory
- kubectl apply -f {CONFIG_FILE} should kick off a job and automatically upload result to S3 as well as slack channel
