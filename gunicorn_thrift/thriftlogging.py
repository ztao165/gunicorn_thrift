# -*- coding: utf-8 -
"""Based on gunicorn.glogging module under MIT license:
2009-2013 (c) Benoît Chesneau <benoitc@e-engura.org>
2009-2013 (c) Paul J. Davis <paul.joseph.davis@gmail.com>

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""

import traceback
import os
import socket

from gunicorn.glogging import Logger

THRIFT_STATUS_CODE = {
    "TIMEOUT": 504,
    "SERVER_ERROR": 500,
    "FUNC_NOT_FOUND": 404,
    "OK": 200,
}


class ThriftLogger(Logger):

    """ThriftLogger class,log access info."""

    def __init__(self, cfg):
        Logger.__init__(self, cfg)
        self.is_statsd = False
        statsd_server = os.environ.get("statsd")
        if statsd_server:
            try:
                host, port = statsd_server.split(":")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.connect((host, int(port)))
            except Exception:
                self.sock = None
            else:
                self.is_statsd = True

    def atoms(self, address, func_name, status, finish):
        atoms = {
            'h': address[0],
            't': self.now(),
            'n': func_name,
            's': THRIFT_STATUS_CODE[status],
            'T': finish * 1000,
            'p': "<%s>" % os.getpid()
        }
        return atoms

    def access(self, address, func_name, status, finish):
        # logger_config_from_dict is used for on_staring-hook load
        # logging-config from dict.
        if not self.cfg.accesslog and not self.cfg.logconfig and not getattr(self, "logger_config_from_dict", None):
            return
        atoms = self.atoms(address, func_name, status, finish)
        access_log_format = "%(h)s %(t)s %(n)s %(s)s %(T)s %(p)s"
        try:
            self.access_log.info(access_log_format % atoms)
            if self.is_statsd:
                project_name = self.cfg.proc_name.split(":")[0]
                statsd_key_base = "thrift.{0}.{1}".format(
                    project_name, func_name)
                self.increment(
                    "{0}.{1}".format(statsd_key_base, atoms["s"]), 1)
                self.histogram(statsd_key_base, atoms["T"])
        except:
            self.error(traceback.format_exc())

    def increment(self, name, value, sampling_rate=1.0):
        try:
            if self.sock:
                self.sock.send(
                    "{0}:{1}|c|@{2}".format(name, value, sampling_rate))
        except Exception:
            pass

    def histogram(self, name, value):
        try:
            if self.sock:
                self.sock.send("{0}:{1}|ms".format(name, value))
        except Exception:
            pass


class WebStatsdLogger(Logger):

    """ThriftLogger class,log access info."""

    def __init__(self, cfg):
        Logger.__init__(self, cfg)
        self.is_statsd = False
        statsd_server = os.environ.get("statsd")
        if statsd_server:
            try:
                host, port = statsd_server.split(":")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.connect((host, int(port)))
            except Exception:
                self.sock = None
            else:
                self.is_statsd = True

    def increment(self, name, value, sampling_rate=1.0):
        try:
            if self.sock:
                self.sock.send(
                    "{0}:{1}|c|@{2}".format(name, value, sampling_rate))
        except Exception:
            pass

    def histogram(self, name, value):
        try:
            if self.sock:
                self.sock.send("{0}:{1}|ms".format(name, value))
        except Exception:
            pass

    def access(self, resp, req, environ, request_time):
        """ See http://httpd.apache.org/docs/2.0/logs.html#combined
        for format details
        """

        if not self.cfg.accesslog and not self.cfg.logconfig:
            return

        # wrap atoms:
        # - make sure atoms will be test case insensitively
        # - if atom doesn't exist replace it by '-'
        safe_atoms = self.atoms_wrapper_class(self.atoms(resp, req, environ,
                                                         request_time))

        try:
            self.access_log.info(self.cfg.access_log_format % safe_atoms)
            if self.is_statsd:
                statsd_key_base = "web.{0}.{1}".format(
                    environ['RAW_URI'].split("?")[0], environ['REQUEST_METHOD'])
                self.increment(
                    "{0}.{1}".format(statsd_key_base, safe_atoms["s"]), 1)
                self.histogram(statsd_key_base, safe_atoms["D"] / 1000.0)
        except:
            self.error(traceback.format_exc())
