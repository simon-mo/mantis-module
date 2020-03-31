docker:
	cd python;docker build -t fissure/py:latest .
	cd ctls; docker build -t fissure/controller:latest .
	docker build -t fissure/redis:latest .

	docker push fissure/py:latest
	docker push fissure/redis:latest
	docker push fissure/controller:latest
	

