# Copyright 2013-2014 DataStax, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from cassandra.query import dict_factory

try:
    import unittest2 as unittest
except ImportError:
    import unittest # noqa

import logging
log = logging.getLogger(__name__)

from collections import namedtuple

from cassandra.cluster import Cluster, UserTypeDoesNotExist

from tests.integration import get_server_versions, PROTOCOL_VERSION


class TypeTests(unittest.TestCase):

    def setUp(self):
        if PROTOCOL_VERSION < 3:
            raise unittest.SkipTest("v3 protocol is required for UDT tests")

        self._cass_version, self._cql_version = get_server_versions()

    def test_unprepared_registered_udts(self):
        c = Cluster(protocol_version=PROTOCOL_VERSION)
        s = c.connect()

        s.execute("""
            CREATE KEYSPACE udt_test_unprepared_registered
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_unprepared_registered")
        s.execute("CREATE TYPE user (age int, name text)")
        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        User = namedtuple('user', ('age', 'name'))
        c.register_user_type("udt_test_unprepared_registered", "user", User)

        s.execute("INSERT INTO mytable (a, b) VALUES (%s, %s)", (0, User(42, 'bob')))
        result = s.execute("SELECT b FROM mytable WHERE a=0")
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual(42, row.b.age)
        self.assertEqual('bob', row.b.name)
        self.assertTrue(type(row.b) is User)

        # use the same UDT name in a different keyspace
        s.execute("""
            CREATE KEYSPACE udt_test_unprepared_registered2
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_unprepared_registered2")
        s.execute("CREATE TYPE user (state text, is_cool boolean)")
        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        User = namedtuple('user', ('state', 'is_cool'))
        c.register_user_type("udt_test_unprepared_registered2", "user", User)

        s.execute("INSERT INTO mytable (a, b) VALUES (%s, %s)", (0, User('Texas', True)))
        result = s.execute("SELECT b FROM mytable WHERE a=0")
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual('Texas', row.b.state)
        self.assertEqual(True, row.b.is_cool)
        self.assertTrue(type(row.b) is User)

        c.shutdown()

    def test_register_before_connecting(self):
        User1 = namedtuple('user', ('age', 'name'))
        User2 = namedtuple('user', ('state', 'is_cool'))

        c = Cluster(protocol_version=PROTOCOL_VERSION)
        s = c.connect()

        s.execute("""
            CREATE KEYSPACE udt_test_register_before_connecting
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_register_before_connecting")
        s.execute("CREATE TYPE user (age int, name text)")
        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        s.execute("""
            CREATE KEYSPACE udt_test_register_before_connecting2
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_register_before_connecting2")
        s.execute("CREATE TYPE user (state text, is_cool boolean)")
        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        # now that types are defined, shutdown and re-create Cluster
        c.shutdown()
        c = Cluster(protocol_version=PROTOCOL_VERSION)
        c.register_user_type("udt_test_register_before_connecting", "user", User1)
        c.register_user_type("udt_test_register_before_connecting2", "user", User2)

        s = c.connect()

        s.set_keyspace("udt_test_register_before_connecting")
        s.execute("INSERT INTO mytable (a, b) VALUES (%s, %s)", (0, User1(42, 'bob')))
        result = s.execute("SELECT b FROM mytable WHERE a=0")
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual(42, row.b.age)
        self.assertEqual('bob', row.b.name)
        self.assertTrue(type(row.b) is User1)

        # use the same UDT name in a different keyspace
        s.set_keyspace("udt_test_register_before_connecting2")
        s.execute("INSERT INTO mytable (a, b) VALUES (%s, %s)", (0, User2('Texas', True)))
        result = s.execute("SELECT b FROM mytable WHERE a=0")
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual('Texas', row.b.state)
        self.assertEqual(True, row.b.is_cool)
        self.assertTrue(type(row.b) is User2)

        c.shutdown()

    def test_prepared_unregistered_udts(self):
        c = Cluster(protocol_version=PROTOCOL_VERSION)
        s = c.connect()

        s.execute("""
            CREATE KEYSPACE udt_test_prepared_unregistered
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_prepared_unregistered")
        s.execute("CREATE TYPE user (age int, name text)")
        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        User = namedtuple('user', ('age', 'name'))
        insert = s.prepare("INSERT INTO mytable (a, b) VALUES (?, ?)")
        s.execute(insert, (0, User(42, 'bob')))

        select = s.prepare("SELECT b FROM mytable WHERE a=?")
        result = s.execute(select, (0,))
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual(42, row.b.age)
        self.assertEqual('bob', row.b.name)

        # use the same UDT name in a different keyspace
        s.execute("""
            CREATE KEYSPACE udt_test_prepared_unregistered2
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_prepared_unregistered2")
        s.execute("CREATE TYPE user (state text, is_cool boolean)")
        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        User = namedtuple('user', ('state', 'is_cool'))
        insert = s.prepare("INSERT INTO mytable (a, b) VALUES (?, ?)")
        s.execute(insert, (0, User('Texas', True)))

        select = s.prepare("SELECT b FROM mytable WHERE a=?")
        result = s.execute(select, (0,))
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual('Texas', row.b.state)
        self.assertEqual(True, row.b.is_cool)

        c.shutdown()

    def test_prepared_registered_udts(self):
        c = Cluster(protocol_version=PROTOCOL_VERSION)
        s = c.connect()

        s.execute("""
            CREATE KEYSPACE udt_test_prepared_registered
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_prepared_registered")
        s.execute("CREATE TYPE user (age int, name text)")
        User = namedtuple('user', ('age', 'name'))
        c.register_user_type("udt_test_prepared_registered", "user", User)

        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        insert = s.prepare("INSERT INTO mytable (a, b) VALUES (?, ?)")
        s.execute(insert, (0, User(42, 'bob')))

        select = s.prepare("SELECT b FROM mytable WHERE a=?")
        result = s.execute(select, (0,))
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual(42, row.b.age)
        self.assertEqual('bob', row.b.name)
        self.assertTrue(type(row.b) is User)

        # use the same UDT name in a different keyspace
        s.execute("""
            CREATE KEYSPACE udt_test_prepared_registered2
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1' }
            """)
        s.set_keyspace("udt_test_prepared_registered2")
        s.execute("CREATE TYPE user (state text, is_cool boolean)")
        User = namedtuple('user', ('state', 'is_cool'))
        c.register_user_type("udt_test_prepared_registered2", "user", User)

        s.execute("CREATE TABLE mytable (a int PRIMARY KEY, b user)")

        insert = s.prepare("INSERT INTO mytable (a, b) VALUES (?, ?)")
        s.execute(insert, (0, User('Texas', True)))

        select = s.prepare("SELECT b FROM mytable WHERE a=?")
        result = s.execute(select, (0,))
        self.assertEqual(1, len(result))
        row = result[0]
        self.assertEqual('Texas', row.b.state)
        self.assertEqual(True, row.b.is_cool)
        self.assertTrue(type(row.b) is User)

        c.shutdown()

    def nested_udt_helper(self, udts, i):
        """
        Helper for creating nested udts.
        """

        if i == 0:
            return udts[0](42, 'Bob')
        else:
            return udts[i](self.nested_udt_helper(udts, i - 1))


    def test_nested_registered_udts(self):
        """
        Test for ensuring nested udts are handled correctly.
        """

        if self._cass_version < (2, 1, 0):
            raise unittest.SkipTest("The tuple type was introduced in Cassandra 2.1")

        MAX_NESTING_DEPTH = 4   #TODO: Move to 128, or similar

        c = Cluster(protocol_version=PROTOCOL_VERSION)
        s = c.connect()

        # set the row_factory to dict_factory for programmatically accessing values
        s.row_factory = dict_factory

        s.execute("""CREATE KEYSPACE test_nested_unregistered_udts
            WITH replication = { 'class' : 'SimpleStrategy', 'replication_factor': '1'}""")
        s.set_keyspace("test_nested_unregistered_udts")

        # create the seed udt
        s.execute("CREATE TYPE depth_0 (age int, name text)")

        # create the nested udts
        for i in range(MAX_NESTING_DEPTH):
            s.execute("CREATE TYPE depth_{} (value depth_{})".format(i + 1, i))

        # create a table with multiple sizes of nested udts
        # no need for all nested types, only a spot checked few and the largest one
        s.execute("CREATE TABLE mytable ("
                  "k int PRIMARY KEY, "
                  "v_0 depth_0, "
                  "v_1 depth_1, "
                  "v_2 depth_2, "
                  "v_3 depth_3, "
                  "v_{0} depth_{0})".format(MAX_NESTING_DEPTH))

        # create the udt container
        udts = []

        # create and register the seed udt type
        udt = namedtuple('depth_0', ('age', 'name'))
        udts.append(udt)
        c.register_user_type("test_nested_unregistered_udts", "depth_0", udts[0])

        # create and register the nested udt types
        for i in range(MAX_NESTING_DEPTH):
            udt = namedtuple('depth_{}'.format(i + 1), ('value'))
            udts.append(udt)
            c.register_user_type("test_nested_unregistered_udts", "depth_{}".format(i + 1), udts[i + 1])

        # verify inserts and reads
        for i in (0, 1, 2, 3, MAX_NESTING_DEPTH):
            # create udt
            udt = self.nested_udt_helper(udts, i)

            # write udt
            s.execute("INSERT INTO mytable (k, v_%s) VALUES (0, %s)", (i, udt))

            # verify udt was written and read correctly
            result = s.execute("SELECT v_%s FROM mytable WHERE k=0", (i,))[0]
            self.assertEqual(udt, result['v_%s' % i])

    def test_nested_unregistered_udts(self):
        """
        Test for ensuring nested unregistered udts are handled correctly.
        """

        # is this even possible?
        pass

    def test_non_existing_types(self):
        c = Cluster(protocol_version=PROTOCOL_VERSION)
        c.connect()
        User = namedtuple('user', ('age', 'name'))
        self.assertRaises(UserTypeDoesNotExist, c.register_user_type, "some_bad_keyspace", "user", User)
        self.assertRaises(UserTypeDoesNotExist, c.register_user_type, "system", "user", User)
