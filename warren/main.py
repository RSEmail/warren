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
from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError

from warren import __version__


def _log_error():
    exc_type, exc_val, exc_tv = sys.exc_info()
    msg = '{0}: {1!s}'.format(exc_type.__name__, exc_val)
    logging.error(msg)


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

    def _trim_quotes(self, node):
        if node.startswith("'") and node.endswith("'"):
            return node[1:-1]
        else:
            return node

    def get_cluster_status(self):
        output = self._run_rabbitmqctl(['cluster_status'])
        match = re.match('^Cluster status of node (.*) ...$', output[0])
        if match:
            local_node = self._trim_quotes(match.group(1))
        else:
            raise Exception('Unexpected header line: {0!r}'.format(output[0]))
        cluster_info = ''.join(output[1:-1])
        match = re.search(r'{nodes,\[((?:{.*?\[.*?\]},?)+)\]}', cluster_info)
        if not match:
            msg = 'Could not parse cluster info: {0!r}'.format(cluster_info)
            raise Exception(msg)
        node_info = match.group(1)
        nodes = set()
        for match in re.finditer(r'{.*?,\[(.*?)\]}', node_info):
            for node_name in match.group(1).split(','):
                nodes.add(self._trim_quotes(node_name))
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
            logging.error('Could not stop RabbitMQ app.')
        args = ['forget_cluster_node', node_name]
        self._run_rabbitmqctl(['forget_cluster_node', node_name])
        try:
            self._run_rabbitmqctl(['start_app'], node_name)
        except Exception as exc:
            logging.error('Could not start RabbitMQ app.')


def main():
    usage = 'Usage: %prog [options] [nodes...]'
    version = '%prog '+__version__
    description = 'Checks the current cluster status of the RabbitMQ node. ' \
        'If the node is unclustered, warren attempts to cluster with the ' \
        'given list of RabbitMQ nodes. Nodes can be provided on the ' \
        'command line or by config file. Config files look for a ' \
        'comma delimited list \'nodes\' under section \'[warren]\'.'
    parser = OptionParser(usage=usage, description=description,
                          version=version)
    parser.add_option('--verbose', action='store_true',
                      help='Enable verbose output.')
    parser.add_option('--config', metavar='FILE',
                      default='/etc/rabbitmq/warren.conf',
                      help='Check for nodes in this config file, '
                      'default %default.')
    parser.add_option('--forget-node', action='append', metavar='NODE',
                      help='Permanently NODE from the cluster. '
                      'Use with caution.')
    options, extra = parser.parse_args()
    expected_nodes = set(extra)

    cfg = SafeConfigParser()
    cfg.read([options.config])

    try:
        cfg_nodes = cfg.get('warren', 'nodes')
    except (NoSectionError, NoOptionError):
        pass
    else:
        for node in cfg_nodes.split(','):
            expected_nodes.add(node.strip())

    if options.verbose:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    ctl = RabbitMQCtl()

    if options.forget_node:
        for node in options.forget_node:
            try:
                ctl.forget_cluster_node(node)
            except Exception as exc:
                _log_error()
                sys.exit(2)

    try:
        local_node, cluster_nodes = ctl.get_cluster_status()
    except Exception as exc:
        _log_error()
        sys.exit(2)
    expected_nodes.add(local_node)

    expected_nodes_str = ', '.join(expected_nodes)
    cluster_nodes_str = ', '.join(cluster_nodes)
    logging.info('Expected cluster nodes: {0}'.format(expected_nodes_str))
    logging.info('Local cluster node: {0}'.format(local_node))
    logging.info('Current cluster nodes: {0}'.format(cluster_nodes_str))

    if cluster_nodes == expected_nodes:
        logging.info('This node is clustered correctly.')

    elif len(cluster_nodes) == 1:
        for node_name in expected_nodes:
            if node_name != local_node:
                logging.info('Attempting to join with: {0}'.format(node_name))
                try:
                    ctl.join_cluster(node_name)
                    break
                except Exception as exc:
                    _log_error()
        else:
            logging.warning('Node could not be clustered.')
            sys.exit(2)


# vim:et:fdm=marker:sts=4:sw=4:ts=4
