#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
 

all: all-subdirs default-all

export TOPDIR = $(shell pwd)
export DISTDIR = $(TOPDIR)/catalog-service-$(VERSION)

all-subdirs:
	for d in $(MAKEALLSUBDIRS); do make -C $$d DIR=$$d || exit 1; done

SUBDIRS = catalogService pylint rmake_plugins xsd
MAKEALLSUBDIRS=catalogService

dist_files = $(extra_files)

.PHONY: clean dist install subdirs

subdirs: default-subdirs

install: install-subdirs

clean: clean-subdirs default-clean

dist:
	if ! grep "^Changes in $(VERSION)" NEWS > /dev/null 2>&1; then \
		echo "no NEWS entry"; \
		exit 1; \
	fi
	$(MAKE) forcedist


archive:
	hg --config 'ui.archivemeta=False' archive --exclude .hgignore -t tbz2 $(DISTDIR).tar.bz2

forcedist: archive

tag:
	hg tag -f catalog-service-$(VERSION)

clean: clean-subdirs default-clean
	@rm -rf $(DISTDIR).tar.bz2

include Make.rules
include Make.defs
 
# vim: set sts=8 sw=8 noexpandtab :
