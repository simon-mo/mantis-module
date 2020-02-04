
# find the OS
uname_S := $(shell sh -c 'uname -s 2>/dev/null || echo not')

# Compile flags for linux / osx
ifeq ($(uname_S),Linux)
	SHOBJ_CFLAGS ?= -W -Wall -fno-common -g -ggdb -std=c++17 -O2 -Iinclude -I${HOME}/.local/include
	SHOBJ_LDFLAGS ?= -shared -L${HOME}/.local/lib
else
	SHOBJ_CFLAGS ?= -W -Wall -dynamic -fno-common -g -ggdb -std=c++17 -O2  -Iinclude
	SHOBJ_LDFLAGS ?= -bundle -undefined dynamic_lookup
endif

.SUFFIXES: .c .so .xo .o .cc

all: mantis.so

mantis.xo: mantis.cc 
	g++ -I. $(CFLAGS) $(SHOBJ_CFLAGS) -fPIC -lglog -c $< -o $@

mantis.so: mantis.xo
	g++ -o $@ $< $(SHOBJ_LDFLAGS) $(LIBS) -lglog -lc

clean:
	rm -rf *.xo *.so

format: 
	clang-format -i mantis.cc

run: mantis.so
	redis-server --bind 0.0.0.0 --port 7000 --loadmodule ./mantis.so

cli:
	redis-cli -p 7000

docker:
	cd python;docker build -t fissure/py:latest .
	cd ctls; docker build -t fissure/controller:latest .
	docker build -t fissure/redis:latest .

	docker push fissure/py:latest
	docker push fissure/redis:latest
	docker push fissure/controller:latest
	

