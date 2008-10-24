#
# Copyright (c) 2008 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#
python_files =	$(wildcard *.py)

dist_files = Makefile $(python_files)

all: default-all

install: all pyfiles-install default-install install-subdirs
	$(PYTHON) -c "import compileall; compileall.compile_dir('$(DESTDIR)$(pydir)/catalogService', ddir='$(pydir)/catalogService', quiet=1)"
	$(PYTHON) -OO -c "import compileall; compileall.compile_dir('$(DESTDIR)$(pydir)/catalogService', ddir='$(pydir)/catalogService', quiet=1)"

dist: default-dist

clean: default-clean
	rm -f xmllib_constants.py

include ../../../Make.rules
include ../../../Make.defs
