#
# Copyright (c) rPath, Inc.
#

.PHONY: all install

all: default-all

override sitedir=$(libdir)/rmake3
override DIR=
python_files = $(wildcard *.py)


install: pyfiles-install default-install pyfiles-compile
	#install -d -m0755 $(DESTDIR)/usr/lib64/rmake3
	#install -m0644 *.py $(DESTDIR)/usr/lib64/rmake3
	#$(MAKE) _pyfiles-compile DDIR=/usr/lib64/rmake3

include ../Make.rules
include ../Make.defs
# vim: set sts=8 sw=8 noexpandtab :
