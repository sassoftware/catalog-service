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


def createSchema(db):
    db.loadSchema()
    cu = db.cursor()
    cu.execute("""
        CREATE TABLE target_types (
            target_type_id     %(PRIMARYKEY)s,
            name              TEXT NOT NULL UNIQUE,
            description       TEXT NOT NULL,
            created_date      TIMESTAMP WITH TIME ZONE NOT NULL
                DEFAULT current_timestamp,
            modified_date     TIMESTAMP WITH TIME ZONE NOT NULL
                DEFAULT current_timestamp
            ) %(TABLEOPTS)s""" % db.keywords)
    query = "INSERT INTO target_types (name, description) VALUES (?, ?)"
    cu.execute(query, "ec2", "Amazon Elastic Compute Cloud")
    cu.execute(query, "eucalyptus", "Eucalyptus")
    cu.execute(query, "openstack", "OpenStack")
    cu.execute(query, "vcloud", "VMware vCloud")
    cu.execute(query, "vmware", "VMware ESX/vSphere")
    cu.execute(query, "xen-enterprise", "Citrix Xen Server")

    cu.execute("""
            CREATE TABLE Targets (
                targetId        %(PRIMARYKEY)s,
                target_type_id  integer            NOT NULL
                    REFERENCES target_types (target_type_id)
                    ON DELETE CASCADE,
                name            varchar(255)        NOT NULL
            ) %(TABLEOPTS)s""" % db.keywords)
    db.tables['Targets'] = []
    cu.execute("""
            CREATE TABLE TargetData (
                targetId        integer             NOT NULL
                    REFERENCES Targets ON DELETE CASCADE,
                name            varchar(255)        NOT NULL,
                value           text,

                PRIMARY KEY ( targetId, name )
            ) %(TABLEOPTS)s """ % db.keywords)
    db.tables['TargetData'] = []
    cu.execute("""
        CREATE TABLE Users (
            userId              %(PRIMARYKEY)s,
            username            varchar(128)    NOT NULL    UNIQUE,
            fullName            varchar(128)    NOT NULL    DEFAULT '',
            passwd              varchar(254),
            email               varchar(128),
            active              smallint,
            admin               smallint        DEFAULT 0
        ) %(TABLEOPTS)s""" % db.keywords)
    db.tables['Users'] = []
    cu.execute("""
        CREATE TABLE TargetUserCredentials (
            targetId        integer             NOT NULL
                REFERENCES Targets ON DELETE CASCADE,
            userId          integer             NOT NULL
                REFERENCES Users ON DELETE CASCADE,
            credentials     text,
            PRIMARY KEY ( targetId, userId )
        ) %(TABLEOPTS)s """ % db.keywords)
    db.tables['TargetUserCredentials'] = []
    from mint.db import schema
    schema._createInventorySchema(db)
    schema._createJobsSchema(db)
    db.loadSchema()
