#
# Copyright (c) 2011111111110 rPath, Inc.
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

dist_files = Makefile $(SCHEMA_FILES)
SCHEMA_FILES = $(wildcard *.xsd)

all: default-all

install: default-install $(DESTDIR)$(datadir)/catalog-service
	install $(SCHEMA_FILES) $(DESTDIR)$(datadir)/catalog-service

$(DESTDIR)$(datadir)/catalog-service:
	install -d -m755 $@

validate-schema:
	xmllint -schema http://www.w3.org/2001/XMLSchema.xsd $(SCHEMA_FILES) > /dev/null

dist: default-dist

clean: default-clean

export TOPDIR=$(shell pwd)/..
include $(TOPDIR)/Make.rules
include $(TOPDIR)/Make.defs
