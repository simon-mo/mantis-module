FROM ubuntu:18.04
RUN apt-get update
RUN apt-get install -y build-essential redis-server libgoogle-glog-dev
COPY include/json.hpp Makefile mantis.cc include/redismodule.h ./
RUN make -j

CMD ["redis-server", "--bind", "0.0.0.0", "--port", "7000", "--loadmodule", "./mantis.so"]