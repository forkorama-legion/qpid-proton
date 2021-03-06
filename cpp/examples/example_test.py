#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License
#

# Run the C++ examples and verify that they behave as expected.
# Example executables must be in PATH

import unittest, sys, time, re, shutil, os
from os.path import dirname
from string import Template

import subprocess

class Server(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        self.port = None
        self.kill_me = kwargs.pop('kill_me', False)
        kwargs.update({'universal_newlines': True,
                       'stdout': subprocess.PIPE,
                       'stderr': subprocess.STDOUT})
        super(Server, self).__init__(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.kill_me:
            self.kill()
            self.stdout.close() # Doesn't get closed if killed
        self.wait()

    @property
    def addr(self):
        if not self.port:
            line = self.stdout.readline()
            self.port = re.search("listening on ([0-9]+)$", line).group(1)
        return ":%s/example" % self.port

def check_output(*args, **kwargs):
    kwargs.update({'universal_newlines': True})
    return subprocess.check_output(*args, **kwargs)

def _cyrusSetup(conf_dir):
  """Write out simple SASL config.tests
  """
  saslpasswd = os.getenv('SASLPASSWD')
  if saslpasswd:
    t = Template("""sasldb_path: ${db}
mech_list: EXTERNAL DIGEST-MD5 SCRAM-SHA-1 CRAM-MD5 PLAIN ANONYMOUS
""")
    abs_conf_dir = os.path.abspath(conf_dir)
    shutil.rmtree(abs_conf_dir, True)
    os.mkdir(abs_conf_dir)
    db = os.path.join(abs_conf_dir,'proton.sasldb')
    conf = os.path.join(abs_conf_dir,'proton-server.conf')
    with open(conf, 'w') as f:
        f.write(t.substitute(db=db))
    cmd_template = Template("echo password | ${saslpasswd} -c -p -f ${db} -u proton user")
    cmd = cmd_template.substitute(db=db, saslpasswd=saslpasswd)
    check_output(args=cmd, shell=True)
    os.environ['PN_SASL_CONFIG_PATH'] = abs_conf_dir

# Globally initialize Cyrus SASL configuration
_cyrusSetup('sasl-conf')

def wait_listening(p):
    return re.search(b"listening on ([0-9]+)$", p.stdout.readline()).group(1)

class Broker(Server):
  def __init__(self):
    super(Broker, self).__init__(["broker", "-a", "//:0"], kill_me=True)

CLIENT_EXPECT="""Twas brillig, and the slithy toves => TWAS BRILLIG, AND THE SLITHY TOVES
Did gire and gymble in the wabe. => DID GIRE AND GYMBLE IN THE WABE.
All mimsy were the borogroves, => ALL MIMSY WERE THE BOROGROVES,
And the mome raths outgrabe. => AND THE MOME RATHS OUTGRABE.
"""

def recv_expect():
    return "".join(['{"sequence"=%s}\n' % (i+1) for i in range(100)])

class ContainerExampleTest(unittest.TestCase):
    """Run the container examples, verify they behave as expected."""

    def test_helloworld(self):
      self.assertMultiLineEqual('Hello World!\n', check_output(["helloworld", Broker.addr]))

    def test_simple_send_recv(self):
        self.assertMultiLineEqual("all messages confirmed\n", check_output(["simple_send", "-a", Broker.addr]))
        self.assertMultiLineEqual(recv_expect(), check_output(["simple_recv", "-a", Broker.addr]))

    def test_simple_recv_send(self):
        recv = Server(["simple_recv", "-a", Broker.addr])
        self.assertMultiLineEqual("all messages confirmed\n", check_output(["simple_send", "-a", Broker.addr]))
        self.assertMultiLineEqual(recv_expect(), recv.communicate()[0])

    def test_simple_send_direct_recv(self):
        recv = Server(["direct_recv", "-a", "//:0"])
        self.assertMultiLineEqual("all messages confirmed\n", check_output(["simple_send", "-a", recv.addr]))
        self.assertMultiLineEqual(recv_expect(), recv.communicate()[0])

    def test_simple_recv_direct_send(self):
        send = Server(["direct_send", "-a", "//:0"])
        self.assertMultiLineEqual(recv_expect(), check_output(["simple_recv", "-a", send.addr]))
        self.assertMultiLineEqual("all messages confirmed\n", send.communicate()[0])

    def test_request_response(self):
        with Server(["server", Broker.addr, "example"], kill_me=True) as server:
            self.assertIn("connected to", server.stdout.readline())
            self.assertMultiLineEqual(CLIENT_EXPECT, check_output(["client", "-a", Broker.addr]))

    def test_request_response_direct(self):
        with Server(["server_direct", "-a", "//:0"], kill_me=True) as server:
            self.assertMultiLineEqual(CLIENT_EXPECT, check_output(["client", "-a", server.addr]))

    def test_flow_control(self):
        want="""success: Example 1: simple credit
success: Example 2: basic drain
success: Example 3: drain without credit
success: Example 4: high/low watermark
"""
        self.assertMultiLineEqual(want, check_output(["flow_control", "--quiet"]))

    def test_encode_decode(self):
        want="""
== Array, list and map of uniform type.
array<int>[int(1), int(2), int(3)]
[ 1 2 3 ]
list[int(1), int(2), int(3)]
[ 1 2 3 ]
map{string(one):int(1), string(two):int(2)}
{ one:1 two:2 }
map{string(z):int(3), string(a):int(4)}
[ z:3 a:4 ]
list[string(a), string(b), string(c)]

== List and map of mixed type values.
list[int(42), string(foo)]
[ 42 foo ]
map{int(4):string(four), string(five):int(5)}
{ 4:four five:5 }

== Insert with stream operators.
array<int>[int(1), int(2), int(3)]
list[int(42), boolean(0), symbol(x)]
map{string(k1):int(42), symbol(k2):boolean(0)}
"""
        self.maxDiff = None
        self.assertMultiLineEqual(want, check_output(["encode_decode"]))

    def test_scheduled_send_03(self):
        # Output should be a bunch of "send" lines but can't guarantee exactly how many.
        out = check_output(["scheduled_send_03", "-a", Broker.addr+"scheduled_send", "-t", "0.1", "-i", "0.001"]).split()
        self.assertTrue(len(out) > 0);
        self.assertEqual(["send"]*len(out), out)

    @unittest.skipUnless(os.getenv('HAS_CPP11'), "not a  C++11 build")
    def test_scheduled_send(self):
        out = check_output(["scheduled_send", "-a", Broker.addr+"scheduled_send", "-t", "0.1", "-i", "0.001"]).split()
        self.assertTrue(len(out) > 0);
        self.assertEqual(["send"]*len(out), out)

    def test_message_properties(self):
        expect="""using put/get: short=123 string=foo symbol=sym
using coerce: short(as long)=123
props[short]=123
props[string]=foo
props[symbol]=sym
short=42 string=bar
expected conversion_error: "unexpected type, want: uint got: int"
expected conversion_error: "unexpected type, want: uint got: string"
"""
        self.assertMultiLineEqual(expect, check_output(["message_properties"]))

    @unittest.skipUnless(os.getenv('HAS_CPP11'), "not a  C++11 build")
    def test_multithreaded_client(self):
        got = check_output(["multithreaded_client", Broker.addr, "examples", "10"])
        self.maxDiff = None
        self.assertIn("10 messages sent and received", got);

#    @unittest.skipUnless(os.getenv('HAS_CPP11'), "not a  C++11 build")
    @unittest.skip("Test is unstable, will enable when fixed")
    def test_multithreaded_client_flow_control(self):
        got = check_output(["multithreaded_client_flow_control", Broker.addr, "examples", "10", "2"])
        self.maxDiff = None
        self.assertIn("20 messages sent and received", got);

class ContainerExampleSSLTest(unittest.TestCase):
    """Run the SSL container examples, verify they behave as expected."""

    def ssl_certs_dir(self):
        """Absolute path to the test SSL certificates"""
        return os.path.join(dirname(sys.argv[0]), "ssl-certs")

    def test_ssl(self):
        # SSL without SASL, VERIFY_PEER_NAME
        out = check_output(["ssl", "-c", self.ssl_certs_dir()])
        expect = "Server certificate identity CN=test_server\nHello World!"
        self.assertIn(expect, out)

    def test_ssl_no_name(self):
        out = check_output(["ssl", "-c", self.ssl_certs_dir(), "-v", "noname"])
        expect = "Outgoing client connection connected via SSL.  Server certificate identity CN=test_server\nHello World!"
        self.assertIn(expect, out)

    def test_ssl_bad_name(self):
        # VERIFY_PEER
        out = check_output(["ssl", "-c", self.ssl_certs_dir(), "-v", "fail"])
        expect = "Expected failure of connection with wrong peer name"
        self.assertIn(expect, out)

    def test_ssl_client_cert(self):
        # SSL with SASL EXTERNAL
        expect="""Inbound client certificate identity CN=test_client
Outgoing client connection connected via SSL.  Server certificate identity CN=test_server
Hello World!
"""
        out = check_output(["ssl_client_cert", self.ssl_certs_dir()])
        self.assertIn(expect, out)

if __name__ == "__main__":
    with Broker() as b:
      Broker.addr = b.addr
      unittest.main()
