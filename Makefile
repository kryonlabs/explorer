ZIRAN ?= ./scripts/ziran.sh
CC ?= cc
export LDLIBS := $(LDLIBS) -lxcb

SOURCES := $(wildcard src/*.zi) $(wildcard tests/*.zi) ziran.toml ziran.lock scripts/ziran.sh
NATIVE_FLAGS := -std=c99 -O2 -ffunction-sections -fdata-sections -Wl,--gc-sections
HOST_TEST_ENV := python3 tests/private_desktop.py --headless env -u GTK_THEME HOME=$(CURDIR)/build/host-test-fixture XDG_CONFIG_HOME=$(CURDIR)/build/host-test-fixture/config XDG_DATA_HOME=$(CURDIR)/build/host-test-fixture/data-home

.PHONY: build check test test-ui test-installed test-file-clipboard run install clean test-saved

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
	python3 tests/private_desktop.py --headless env XDG_DATA_HOME=$(CURDIR)/build/model-test-fixture/data-home build/model-test $(CURDIR)/build/model-test-fixture
	$(HOST_TEST_ENV) build/host-test $(CURDIR)/build/host-test-fixture
	$(MAKE) test-saved

test-saved:
	build-queue -- $(ZIRAN) ir --project --entry model_test:main -o build/model-test-ir tests/model_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry model_test:main -o build/model-test-saved-c build/model-test-ir/model_test.zir
	python3 tests/private_desktop.py --headless env XDG_DATA_HOME=$(CURDIR)/build/model-test-fixture/data-home build/model-test-saved-c/model_test $(CURDIR)/build/model-test-fixture
	build-queue -- $(ZIRAN) ir --project --entry host_test:main -o build/host-test-ir tests/host_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry host_test:main -o build/host-test-saved-c build/host-test-ir/host_test.zir
	$(HOST_TEST_ENV) build/host-test-saved-c/host_test $(CURDIR)/build/host-test-fixture

test-ui: build
	python3 tests/private_desktop.py python3 tests/ui_test.py

build/file-clipboard-probe: $(SOURCES)
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry file_clipboard_probe:main -o build/file-clipboard-probe-c tests/file_clipboard_probe.zi
	cp build/file-clipboard-probe-c/file_clipboard_probe build/file-clipboard-probe
	build-queue -- $(ZIRAN) ir --project --entry file_clipboard_probe:main -o build/file-clipboard-probe-ir tests/file_clipboard_probe.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry file_clipboard_probe:main -o build/file-clipboard-probe-saved-c build/file-clipboard-probe-ir/file_clipboard_probe.zir

test-file-clipboard: build build/file-clipboard-probe
	python3 tests/private_desktop.py python3 tests/file_clipboard_test.py

test-installed:
	python3 tests/private_desktop.py python3 tests/ui_test.py --executable "$(HOME)/.local/bin/shelf" --capture-prefix installed-ui

install:
	build-queue -- $(ZIRAN) install

clean:
	rm -rf build
