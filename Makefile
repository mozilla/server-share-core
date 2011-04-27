ifeq ($(OS),Windows_NT)
BIN_DIR = Scripts
else
BIN_DIR = bin
endif

APPNAME = server-share-core
PKGNAME = linkoauth
DEPS = mozilla:server-core

VIRTUALENV = virtualenv
NOSE = $(BIN_DIR)/nosetests
NOSETESTS_ARGS = -s
NOSETESTS_ARGS_C = -s --with-xunit --with-coverage --cover-package=$(PKGNAME) --cover-erase
TESTS = $(PKGNAME)/tests
PYTHON = $(BIN_DIR)/python
version = $(shell $(PYTHON) setup.py --version)
#tag = $(shell grep tag_build setup.cfg  | cut -d= -f2 | xargs echo )

# *sob* - just running easy_install on Windows prompts for UAC...
ifeq ($(OS),Windows_NT)
EZ = $(PYTHON) $(BIN_DIR)/easy_install-script.py
else
EZ = $(BIN_DIR)/easy_install
endif

COVEROPTS = --cover-html --cover-html-dir=html --with-coverage --cover-package=$(PKGNAME)
COVERAGE := coverage
PYLINT = $(BIN_DIR)/pylint

all: build

clean:
	rm -rf $(objdir)
	rm -rf $(static_dir)
	rm -rf $(dist_dir)
	rm -f $(APPNAME).spec

dist:   server-share-core.spec
	$(PYTHON) setup.py sdist --formats gztar,zip
	# This is so Hudson can get stable urls to this tarball
	ln -sf $(PKGNAME)-$(version).tar.gz dist/$(PKGNAME)-current.tar.gz

rpm:	server-share-core.spec
	$(PYTHON) setup.py bdist_rpm

$(APPNAME).spec: $(APPNAME).spec.in Makefile tools/makespec
	tools/makespec $(version)$(tag) linkoauth.egg-info/requires.txt < $(APPNAME).spec.in > $(APPNAME).spec

build:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(PYTHON) build.py $(APPNAME) $(DEPS)
	$(PYTHON) setup.py develop

test:
	$(EZ) mock
	$(NOSE) $(NOSETESTS_ARGS) $(TESTS)

coverage:
	$(EZ) coverage
	$(NOSE) $(NOSETESTS_ARGS_C) $(TESTS)
	$(COVERAGE) xml -i

.PHONY: clean dist rpm build test coverage
