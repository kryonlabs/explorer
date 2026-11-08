ZIRAN ?= ./scripts/ziran.sh
CC ?= cc
export LDLIBS := $(LDLIBS) -lxcb

SOURCES := $(wildcard src/*.zi) $(wildcard tests/*.zi) ziran.toml ziran.lock scripts/ziran.sh
NATIVE_FLAGS := -std=c99 -O2 -ffunction-sections -fdata-sections -Wl,--gc-sections
HOST_TEST_ENV := python3 tests/private_desktop.py --headless env -u GTK_THEME HOME=$(CURDIR)/build/host-test-fixture XDG_CONFIG_HOME=$(CURDIR)/build/host-test-fixture/config XDG_DATA_HOME=$(CURDIR)/build/host-test-fixture/data-home

.PHONY: test-split test-split-native test-tabs test-tabs-native build check test test-ui test-installed test-file-clipboard test-filenames test-bookmarks test-bookmarks-native test-tree test-tree-native test-location test-location-native run install clean test-saved

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

test-filenames: build
	python3 tests/private_desktop.py python3 tests/filename_test.py

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

build/bookmarks-test: $(SOURCES)
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry bookmarks_test:main -o build/bookmarks-test-c tests/bookmarks_test.zi
	cp build/bookmarks-test-c/bookmarks_test build/bookmarks-test

test-bookmarks-native: build/bookmarks-test
	python3 tests/private_desktop.py --headless env HOME=$(CURDIR)/build/bookmarks-test-fixture/home XDG_CONFIG_HOME=$(CURDIR)/build/bookmarks-test-fixture/config build/bookmarks-test $(CURDIR)/build/bookmarks-test-fixture
	build-queue -- $(ZIRAN) ir --project --entry bookmarks_test:main -o build/bookmarks-test-ir tests/bookmarks_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry bookmarks_test:main -o build/bookmarks-test-saved-c build/bookmarks-test-ir/bookmarks_test.zir
	python3 tests/private_desktop.py --headless env HOME=$(CURDIR)/build/bookmarks-test-fixture/home XDG_CONFIG_HOME=$(CURDIR)/build/bookmarks-test-fixture/config build/bookmarks-test-saved-c/bookmarks_test $(CURDIR)/build/bookmarks-test-fixture

test-bookmarks: build test-bookmarks-native
	python3 tests/private_desktop.py python3 tests/bookmarks_test.py

build/tree-sidebar-test: $(SOURCES)
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry tree_sidebar_test:main -o build/tree-sidebar-test-c tests/tree_sidebar_test.zi
	cp build/tree-sidebar-test-c/tree_sidebar_test build/tree-sidebar-test

test-tree-native: build/tree-sidebar-test
	python3 tests/private_desktop.py --headless build/tree-sidebar-test $(CURDIR)/build/tree-test-fixture
	build-queue -- $(ZIRAN) ir --project --entry tree_sidebar_test:main -o build/tree-sidebar-test-ir tests/tree_sidebar_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry tree_sidebar_test:main -o build/tree-sidebar-test-saved-c build/tree-sidebar-test-ir/tree_sidebar_test.zir
	python3 tests/private_desktop.py --headless build/tree-sidebar-test-saved-c/tree_sidebar_test $(CURDIR)/build/tree-test-fixture

test-tree: build test-tree-native
	python3 tests/private_desktop.py python3 tests/tree_sidebar_test.py

build/location-test: $(SOURCES)
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry location_test:main -o build/location-test-c tests/location_test.zi
	cp build/location-test-c/location_test build/location-test

test-location-native: build/location-test
	python3 tests/private_desktop.py --headless build/location-test $(CURDIR)/build/location-test-fixture
	build-queue -- $(ZIRAN) ir --project --entry location_test:main -o build/location-test-ir tests/location_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry location_test:main -o build/location-test-saved-c build/location-test-ir/location_test.zir
	python3 tests/private_desktop.py --headless build/location-test-saved-c/location_test $(CURDIR)/build/location-test-fixture
	python3 tests/private_desktop.py --headless python3 tests/location_oom_test.py $(CURDIR)/build/location-test $(CURDIR)/build/location-test-saved-c/location_test

test-location: build test-location-native
	python3 tests/private_desktop.py python3 tests/location_thunar_probe.py
	python3 tests/private_desktop.py python3 tests/location_test.py

build/tabs-test: $(SOURCES)
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry tabs_test:main -o build/tabs-test-c tests/tabs_test.zi
	cp build/tabs-test-c/tabs_test build/tabs-test

test-tabs-native: build/tabs-test
	python3 tests/private_desktop.py --headless build/tabs-test $(CURDIR)/build/tabs-test-fixture
	build-queue -- $(ZIRAN) ir --project --entry tabs_test:main -o build/tabs-test-ir tests/tabs_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry tabs_test:main -o build/tabs-test-saved-c build/tabs-test-ir/tabs_test.zir
	python3 tests/private_desktop.py --headless build/tabs-test-saved-c/tabs_test $(CURDIR)/build/tabs-test-fixture
	python3 tests/private_desktop.py --headless python3 tests/tabs_failure_test.py $(CURDIR)/build/tabs-test $(CURDIR)/build/tabs-test-saved-c/tabs_test

test-tabs: build test-tabs-native
	python3 tests/private_desktop.py python3 tests/tabs_test.py

build/split-test: $(SOURCES)
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry split_test:main -o build/split-test-c tests/split_test.zi
	cp build/split-test-c/split_test build/split-test

test-split-native: build/split-test
	python3 tests/private_desktop.py --headless build/split-test $(CURDIR)/build/split-test-fixture
	build-queue -- $(ZIRAN) ir --project --entry split_test:main -o build/split-test-ir tests/split_test.zi
	build-queue -- $(ZIRAN) build --project --target=c --exe --entry split_test:main -o build/split-test-saved-c build/split-test-ir/split_test.zir
	python3 tests/private_desktop.py --headless build/split-test-saved-c/split_test $(CURDIR)/build/split-test-fixture
	python3 tests/split_failure_test.py build/split-test build/split-test-saved-c/split_test

test-split: build test-split-native
	python3 tests/private_desktop.py python3 tests/split_test.py
