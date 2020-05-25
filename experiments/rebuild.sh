set -ex

cd ..
./build_docker.sh | tee experiments/templates/container_hash.libsonnet
cd experiments

./cleanup.sh

cd templates
rm configs/*
jsonnet experiments.jsonnet -m configs
cd ..

# kubectl apply -f templates/configs
