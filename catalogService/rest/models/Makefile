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
                --search-path=$(XSD_DIR) \
                -o generateds_$(subst -,_,$(patsubst rule-%,%,$@)).py \
                $(XSD_DIR)/$(patsubst rule-%,%,$@).xsd

include ../../../Make.rules
include ../../../Make.defs
