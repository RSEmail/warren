# The MIT License (MIT)
#
# Copyright (c) 2014 Ian Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import sys
import re
import subprocess
import logging
from socket import getfqdn
from optparse import OptionParser


class RabbitMQCtl(object):

    def __init__(self, rabbitmqctl='rabbitmqctl'):
        super(RabbitMQCtl, self).__init__()
        self.ctl = rabbitmqctl

    def _run_rabbitmqctl(self, args, run_on=None):
        proc_args = [self.ctl] + (['-n', run_on] if run_on else []) + args
        logging.debug('Executing: {0!r}'.format(' '.join(proc_args)))
        proc = subprocess.Popen(proc_args,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            msg = 'Unexpected return code: {0}\n' \
                  '    Stdout: {1!r}\n' \
                  '    Stderr: {2!r}\n'.format(proc.returncode, stdout, stderr)
            raise Exception(msg)
        return stdout.splitlines()

    def get_cluster_status(self):
        output = self._run_rabbitmqctl(['cluster_status'])
        match = re.match('^Cluster status of node (.*) ...$', output[0])
        if match:
            local_node = match.group(1)
        else:
            raise Exception('Unexpected header line: {0!r}'.format(output[0]))
        match = re.match('^...done', output[-1])
        if not match:
            raise Exception('Unexpected footer line: {0!r}'.format(output[-1]))
        cluster_info = ''.join(output[1:-1])
        match = re.search(r'{nodes,\[((?:{.*?\[.*?\]},?)+)\]}', cluster_info)
        if not match:
            msg = 'Could not parse cluster info: {0!r}'.format(cluster_info)
            raise Exception(msg)
        node_info = match.group(1)
        nodes = set()
        for match in re.finditer(r'{.*?,\[(.*?)\]}', node_info):
            nodes |= set(match.group(1).split(','))
        return local_node, nodes

    def join_cluster(self, node_name):
        try:
            self._run_rabbitmqctl(['stop_app'])
            self._run_rabbitmqctl(['join_cluster', node_name])
        finally:
            self._run_rabbitmqctl(['start_app'])

    def forget_cluster_node(self, node_name):
        try:
            self._run_rabbitmqctl(['stop_app'], node_name)
        except Exception as exc:
            logging.error(str(exc))
        args = ['forget_cluster_node', node_name]
        self._run_rabbitmqctl(['forget_cluster_node', node_name])
        try:
            self._run_rabbitmqctl(['reset'], node_name)
            self._run_rabbitmqctl(['start_app'], node_name)
        except Exception as exc:
            logging.error(str(exc))


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    usage = 'Usage: %prog <remote nodes...>'
    parser = OptionParser()
    options, extra = parser.parse_args()
    known_nodes = set(extra)

    ctl = RabbitMQCtl()

    try:
        local_node, cluster_nodes = ctl.get_cluster_status()
    except Exception as exc:
        logging.error(str(exc))
        sys.exit(1)
    known_nodes.add(local_node)

    logging.info('Local cluster node: {0!r}'.format(local_node))
    logging.info('Current cluster nodes: {0!r}'.format(cluster_nodes))
    logging.info('Known cluster nodes: {0!r}'.format(known_nodes))

    if len(cluster_nodes) == 1 and len(known_nodes) > 1:
        for node_name in known_nodes:
            if node_name != local_node:
                logging.info('Attempting to join: {0!r}'.format(node_name))
                try:
                    ctl.join_cluster(node_name)
                    break
                except Exception as exc:
                    logging.error(str(exc))

    elif cluster_nodes > known_nodes:
        unknown_nodes = cluster_nodes - known_nodes
        for node_name in unknown_nodes:
            try:
                ctl.forget_cluster_node(node_name)
            except Exception as exc:
                logging.error(str(exc))


# vim:et:fdm=marker:sts=4:sw=4:ts=4
