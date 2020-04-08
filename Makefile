docker:
	cd python; docker build -t fissure/py:latest .
	cd src; docker build -t fissure/redis:latest .

	docker push fissure/py:latest
	docker push fissure/redis:latest
	

