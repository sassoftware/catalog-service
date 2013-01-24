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
