docker:
	cd python; docker build -t fissure/py:latest .
	cd src; docker build -t fissure/redis:latest .

	docker push fissure/py:latest
	docker push fissure/redis:latest
	
insert-secrets:
	@echo "Don't call this from make, it's just here to document how to use it"
	exit 1
	kubectl create secret generic aws-s3-creds \
		--from-literal=AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		--from-literal=AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)
	
	kubectl create secret generic slack-endpoint --from-literal=SLACK_ENDPOINT=$(SLACK_ENDPOINT)

create-job-mutex:
	# Require `kubectl proxy` first
	curl --header "Content-Type: application/json-patch+json" \
		--request PATCH \
		--data '[{"op": "add", "path": "/status/capacity/mantis.com~1concurrent", "value": "1"}]' \
		http://localhost:8001/api/v1/nodes/ip-192-168-11-95.us-west-2.compute.internal/status

remote-job-mutex:
	curl --header "Content-Type: application/json-patch+json" \
		--request PATCH \
		--data '[{"op": "remove", "path": "/status/capacity/mantis.com~1concurrent"}]' \
		http://localhost:8001/api/v1/nodes/ip-192-168-11-95.us-west-2.compute.internal/status

move-notebook:
	cp /home/ubuntu/notebooks/plot_mantis.ipynb /home/ubuntu/mantis-module/python/mantis/plot_mantis.ipynb