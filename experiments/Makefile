noop:
	@echo "targets: build, clean, gen

build:
	cd ..; \
	bash build_docker.sh | tee experiments/templates/container_hash.libsonnet

gen:
	cd templates; \
	rm configs/*; \
	jsonnet experiments.jsonnet -m configs

clean:
	./cleanup.sh
