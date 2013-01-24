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


'''
rBuilder database schema

This includes rules to create from scratch all tables and indices used
by rBuilder. For migration from previous versions, see the
L{migrate<mint.migrate>} module.
'''

def _addTableRows(db, table, uniqueKey, rows):
    """
    Adds rows to the table, if they do not exist already
    The rows argument is a list of dictionaries
    """
    if not rows:
        return
    cu = db.cursor()
    inserts = []
    sql = "SELECT 1 FROM %s WHERE %s = ?" % (table, uniqueKey)
    tableCols = rows[0].keys()
    for row in rows:
        cu.execute(sql, row[uniqueKey])
        if cu.fetchall():
            continue
        inserts.append(tuple(row[c] for c in tableCols))
    if not inserts:
        return False
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table,
        ','.join(tableCols), ','.join('?' for c in tableCols))
    cu.executemany(sql, inserts)
    return True

def _createInventorySchema(db):
    cu = db.cursor()
    changed = False
    if 'inventory_managed_system' not in db.tables:
        cu.execute("""
            CREATE TABLE "inventory_managed_system" (
                "id" %(PRIMARYKEY)s,
                "registration_date" timestamp with time zone NOT NULL,
                "generated_uuid" varchar(64),
                "local_uuid" varchar(64),
                "ssl_client_certificate" varchar(8092),
                "ssl_client_key" varchar(8092),
                "ssl_server_certificate" varchar(8092)
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['inventory_managed_system'] = []
        changed = True

    if 'inventory_system_target' not in db.tables:
        cu.execute("""
            CREATE TABLE "inventory_system_target" (
                "id" %(PRIMARYKEY)s,
                "managed_system_id" integer
                    REFERENCES "inventory_managed_system" ("id")
                    DEFERRABLE INITIALLY DEFERRED,
                "target_id" integer NOT NULL
                    REFERENCES "targets" ("targetid")
                    DEFERRABLE INITIALLY DEFERRED,
                "target_system_id" varchar(256)
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['inventory_system_target'] = []
        changed = True
    return changed

    if 'inventory_system' not in db.tables:
        cu.execute("""
            CREATE TABLE "inventory_system" (
                "system_id" %(PRIMARYKEY)s,
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['inventory_system'] = []
        changed = True
    return changed


def _createJobsSchema(db):
    cu = db.cursor()
    changed = False

    if 'job_types' not in db.tables:
        cu.execute("""
            CREATE TABLE job_types
            (
                job_type_id %(PRIMARYKEY)s,
                name VARCHAR NOT NULL UNIQUE,
                description VARCHAR NOT NULL
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['job_types'] = []
        changed = True
    changed |= _addTableRows(db, 'job_types', 'name',
        [ dict(name="instance-launch", description='Instance Launch'), 
          dict(name="instance-update", description='Instance Update'), 
          dict(name="image-deployment", description='Image Upload'), 
          dict(name="platform-load", description='Platform Load'),
          dict(name="software-version-refresh", description='Software Version Refresh'), ])

    if 'job_states' not in db.tables:
        cu.execute("""
            CREATE TABLE job_states
            (
                job_state_id %(PRIMARYKEY)s,
                name VARCHAR NOT NULL UNIQUE
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['job_states'] = []
        changed = True
    changed |= _addTableRows(db, 'job_states', 'name', [ dict(name='Queued'),
        dict(name='Running'), dict(name='Completed'), dict(name='Failed') ])

    if 'rest_methods' not in db.tables:
        cu.execute("""
            CREATE TABLE rest_methods
            (
                rest_method_id %(PRIMARYKEY)s,
                name VARCHAR NOT NULL UNIQUE
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['rest_methods'] = []
        changed = True
    changed |= _addTableRows(db, 'rest_methods', 'name', [ dict(name='POST'),
        dict(name='PUT'), dict(name='DELETE') ])

    if 'jobs' not in db.tables:
        cu.execute("""
            CREATE TABLE jobs
            (
                job_id      %(PRIMARYKEY)s,
                job_type_id INTEGER NOT NULL
                    REFERENCES job_types ON DELETE CASCADE,
                job_state_id INTEGER NOT NULL
                    REFERENCES job_states ON DELETE CASCADE,
                job_uuid    VARCHAR(64) NOT NULL UNIQUE,
                created_by   INTEGER NOT NULL
                    REFERENCES Users ON DELETE CASCADE,
                created     NUMERIC(14,4) NOT NULL,
                modified    NUMERIC(14,4) NOT NULL,
                expiration  NUMERIC(14,4),
                ttl         INTEGER,
                pid         INTEGER,
                message     VARCHAR,
                error_response VARCHAR,
                rest_uri    VARCHAR,
                rest_method_id INTEGER
                    REFERENCES rest_methods ON DELETE CASCADE,
                rest_args   VARCHAR
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['jobs'] = []
        changed = True

    if 'job_history' not in db.tables:
        cu.execute("""
            CREATE TABLE job_history
            (
                job_history_id  %(PRIMARYKEY)s,
                -- job_history_type needed
                job_id          INTEGER NOT NULL
                    REFERENCES jobs ON DELETE CASCADE,
                timestamp   NUMERIC(14,3) NOT NULL,
                content     VARCHAR NOT NULL
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['job_history'] = []
        changed = True

    if 'job_results' not in db.tables:
        cu.execute("""
            CREATE TABLE job_results
            (
                job_result_id   %(PRIMARYKEY)s,
                job_id          INTEGER NOT NULL
                    REFERENCES jobs ON DELETE CASCADE,
                data    VARCHAR NOT NULL
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['job_results'] = []
        changed = True

    if 'job_target' not in db.tables:
        cu.execute("""
            CREATE TABLE job_target
            (
                job_id      INTEGER NOT NULL
                    REFERENCES jobs ON DELETE CASCADE,
                targetId    INTEGER NOT NULL
                    REFERENCES Targets ON DELETE CASCADE
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['job_target'] = []
        changed = True

    if 'job_system' not in db.tables:
        cu.execute("""
            CREATE TABLE job_system
            (
                job_id      INTEGER NOT NULL
                    REFERENCES jobs ON DELETE CASCADE,
                system_id    INTEGER NOT NULL
                    REFERENCES inventory_system ON DELETE CASCADE
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['job_system'] = []
        changed = True


    if 'job_managed_system' not in db.tables:
        cu.execute("""
            CREATE TABLE job_managed_system
            (
                job_id      INTEGER NOT NULL
                    REFERENCES jobs ON DELETE CASCADE,
                managed_system_id  INTEGER NOT NULL
                    REFERENCES inventory_managed_systems ON DELETE CASCADE
            ) %(TABLEOPTS)s""" % db.keywords)
        db.tables['job_managed_system'] = []
        changed = True

    return changed
