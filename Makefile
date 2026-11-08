ZIRAN ?= ./scripts/ziran.sh
CC ?= cc

SOURCES := $(wildcard src/*.zi) $(wildcard tests/*.zi) ziran.toml ziran.lock scripts/ziran.sh
NATIVE_FLAGS := -std=c99 -O2 -ffunction-sections -fdata-sections -Wl,--gc-sections
HOST_TEST_ENV := env -u DISPLAY -u WAYLAND_DISPLAY -u WAYLAND_SOCKET -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS -u SESSION_MANAGER -u ICEAUTHORITY -u GTK_THEME YUE_DESKTOP_RECOVERY=0 HOME=$(CURDIR)/build/host-test-fixture XDG_CONFIG_HOME=$(CURDIR)/build/host-test-fixture/config XDG_DATA_HOME=$(CURDIR)/build/host-test-fixture/data-home

.PHONY: build check test test-ui test-installed run install clean test-saved

build:
	build-queue -- $(ZIRAN) build

check:
	build-queue -- $(ZIRAN) check
	build-queue -- $(ZIRAN) check --project src/model.zi
	build-queue -- $(ZIRAN) check --project tests/model_test.zi

run:
	build-queue -- $(ZIRAN) run

build/model-test: $(SOURCES)
	build-queue -- /bin/sh -c \
		'$(ZIRAN) build --project --target=c --entry model_test:main -o build/model-test-c tests/model_test.zi && \
		$(CC) $(NATIVE_FLAGS) -I$$($(ZIRAN) pkg path ziran)/include -Ibuild/model-test-c build/model-test-c/*.c -lm -o build/model-test'

build/host-test: $(SOURCES)
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry host_test:main -o build/host-test-c tests/host_test.zi
	cp build/host-test-c/host_test build/host-test

test: build/model-test build/host-test
	rm -rf build/model-test-fixture
	mkdir -p build/model-test-fixture
	XDG_DATA_HOME=$(CURDIR)/build/model-test-fixture/data-home build/model-test $(CURDIR)/build/model-test-fixture
	$(HOST_TEST_ENV) build/host-test $(CURDIR)/build/host-test-fixture
	$(MAKE) test-saved

test-saved:
	build-queue -- $(ZIRAN) ir --project --entry model_test:main -o build/model-test-ir tests/model_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry model_test:main -o build/model-test-saved-c build/model-test-ir/model_test.zir
	XDG_DATA_HOME=$(CURDIR)/build/model-test-fixture/data-home build/model-test-saved-c/model_test $(CURDIR)/build/model-test-fixture
	build-queue -- $(ZIRAN) ir --project --entry host_test:main -o build/host-test-ir tests/host_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry host_test:main -o build/host-test-saved-c build/host-test-ir/host_test.zir
	$(HOST_TEST_ENV) build/host-test-saved-c/host_test $(CURDIR)/build/host-test-fixture

test-ui: build
	env -u DISPLAY -u WAYLAND_DISPLAY -u WAYLAND_SOCKET -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS -u SESSION_MANAGER -u ICEAUTHORITY YUE_DESKTOP_RECOVERY=0 dbus-run-session -- xvfb-run -a python3 tests/ui_test.py

test-installed:
	env -u DISPLAY -u WAYLAND_DISPLAY -u WAYLAND_SOCKET -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS -u SESSION_MANAGER -u ICEAUTHORITY YUE_DESKTOP_RECOVERY=0 dbus-run-session -- xvfb-run -a python3 tests/ui_test.py --executable "$(HOME)/.local/bin/shelf" --capture-prefix installed-ui

install:
	build-queue -- $(ZIRAN) install

clean:
	rm -rf build
