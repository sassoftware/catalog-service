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
GENERATE_DS=~/hg/generateDS/generateDS.py
XSD_DIR=../../../xsd

dist_files = Makefile $(python_files)

all: default-all

install: all pyfiles-install default-install install-subdirs pyfiles-compile

dist: default-dist

clean: default-clean

generate: $(patsubst $(XSD_DIR)/%.xsd,rule-%,$(wildcard $(XSD_DIR)/*.xsd))

rule-%:
	$(GENERATE_DS) -f --silence \
                --no-dates \
                --no-versions \
                --member-specs=list \
                --external-encoding=utf-8 \
                -o generateds_$(subst -,_,$(patsubst rule-%,%,$@)).py \
                $(XSD_DIR)/$(patsubst rule-%,%,$@).xsd

include ../../../Make.rules
include ../../../Make.defs
