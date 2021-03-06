# Copyright (C) 2015 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Tests for db purge."""

import datetime
import uuid

from oslo_db import exception as db_exc
from oslo_utils import timeutils
from sqlalchemy.dialects import sqlite

from karbor import context
from karbor import db
from karbor.db.sqlalchemy import api as db_api
from karbor import exception
from karbor.tests import base

from oslo_db.sqlalchemy import utils as sqlalchemyutils


class PurgeDeletedTest(base.TestCase):

    def setUp(self):
        super(PurgeDeletedTest, self).setUp()
        self.context = context.get_admin_context()
        self.engine = db_api.get_engine()
        self.session = db_api.get_session()
        self.conn = self.engine.connect()
        self.plans = sqlalchemyutils.get_table(
            self.engine, "plans")
        # The resources table has a FK of plans.id
        self.resources = sqlalchemyutils.get_table(
            self.engine, "resources")

        self.uuidstrs = []
        for unused in range(6):
            self.uuidstrs.append(uuid.uuid4().hex)
        # Add 6 rows to table
        for uuidstr in self.uuidstrs:
            ins_stmt = self.plans.insert().values(id=uuidstr)
            self.conn.execute(ins_stmt)
            ins_stmt = self.resources.insert().values(plan_id=uuidstr)
            self.conn.execute(ins_stmt)

        # Set 4 of them deleted, 2 are 60 days ago, 2 are 20 days ago
        old = timeutils.utcnow() - datetime.timedelta(days=20)
        older = timeutils.utcnow() - datetime.timedelta(days=60)
        make_plans_old = self.plans.update().where(
            self.plans.c.id.in_(self.uuidstrs[1:3])).values(
            deleted_at=old)
        make_plans_older = self.plans.update().where(
            self.plans.c.id.in_(self.uuidstrs[4:6])).values(
            deleted_at=older)
        make_resources_old = self.resources.update().where(
            self.resources.c.plan_id.in_(self.uuidstrs[1:3])).values(
            deleted_at=old)
        make_resources_older = self.resources.update().where(
            self.resources.c.plan_id.in_(self.uuidstrs[4:6])).values(
            deleted_at=older)

        self.conn.execute(make_plans_old)
        self.conn.execute(make_plans_older)
        self.conn.execute(make_resources_old)
        self.conn.execute(make_resources_older)

    def test_purge_deleted_rows_old(self):
        dialect = self.engine.url.get_dialect()
        if dialect == sqlite.dialect:
            # We're seeing issues with foreign key support in SQLite 3.6.20
            # SQLAlchemy doesn't support it at all with < SQLite 3.6.19
            # It works fine in SQLite 3.7.
            # Force foreign_key checking if running SQLite >= 3.7
            import sqlite3
            tup = sqlite3.sqlite_version_info
            if tup[0] > 3 or (tup[0] == 3 and tup[1] >= 7):
                self.conn.execute("PRAGMA foreign_keys = ON")
        # Purge at 30 days old, should only delete 2 rows
        db.purge_deleted_rows(self.context, age_in_days=30)
        plans_rows = self.session.query(self.plans).count()
        resources_rows = self.session.query(self.resources).count()
        # Verify that we only deleted 2
        self.assertEqual(4, plans_rows)
        self.assertEqual(4, resources_rows)

    def test_purge_deleted_rows_older(self):
        dialect = self.engine.url.get_dialect()
        if dialect == sqlite.dialect:
            # We're seeing issues with foreign key support in SQLite 3.6.20
            # SQLAlchemy doesn't support it at all with < SQLite 3.6.19
            # It works fine in SQLite 3.7.
            # Force foreign_key checking if running SQLite >= 3.7
            import sqlite3
            tup = sqlite3.sqlite_version_info
            if tup[0] > 3 or (tup[0] == 3 and tup[1] >= 7):
                self.conn.execute("PRAGMA foreign_keys = ON")
        # Purge at 10 days old now, should delete 2 more rows
        db.purge_deleted_rows(self.context, age_in_days=10)

        plans_rows = self.session.query(self.plans).count()
        resources_rows = self.session.query(self.resources).count()
        # Verify that we only have 2 rows now
        self.assertEqual(2, plans_rows)
        self.assertEqual(2, resources_rows)

    def test_purge_deleted_rows_bad_args(self):
        # Test with no age argument
        self.assertRaises(TypeError, db.purge_deleted_rows, self.context)
        # Test purge with non-integer
        self.assertRaises(exception.InvalidParameterValue,
                          db.purge_deleted_rows, self.context,
                          age_in_days='ten')

    def test_purge_deleted_rows_integrity_failure(self):
        dialect = self.engine.url.get_dialect()
        if dialect == sqlite.dialect:
            # We're seeing issues with foreign key support in SQLite 3.6.20
            # SQLAlchemy doesn't support it at all with < SQLite 3.6.19
            # It works fine in SQLite 3.7.
            # So return early to skip this test if running SQLite < 3.7
            import sqlite3
            tup = sqlite3.sqlite_version_info
            if tup[0] < 3 or (tup[0] == 3 and tup[1] < 7):
                self.skipTest(
                    'sqlite version too old for reliable SQLA foreign_keys')
            self.conn.execute("PRAGMA foreign_keys = ON")

        # add new entry in plans and resources for
        # integrity check
        uuid_str = uuid.uuid4().hex
        ins_stmt = self.plans.insert().values(id=uuid_str)
        self.conn.execute(ins_stmt)
        ins_stmt = self.resources.insert().values(
            plan_id=uuid_str)
        self.conn.execute(ins_stmt)

        # set plans record to deleted 20 days ago
        old = timeutils.utcnow() - datetime.timedelta(days=20)
        make_old = self.plans.update().where(
            self.plans.c.id.in_([uuid_str])).values(deleted_at=old)
        self.conn.execute(make_old)

        # Verify that purge_deleted_rows fails due to Foreign Key constraint
        self.assertRaises(db_exc.DBReferenceError, db.purge_deleted_rows,
                          self.context, age_in_days=10)
