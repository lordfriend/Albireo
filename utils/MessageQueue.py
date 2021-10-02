import json
import logging

import pika
import yaml
from pika.adapters.twisted_connection import TwistedProtocolConnection
from twisted.internet import protocol, reactor, defer, task

AMQP_DEFAULT_PORT = 5672
AMQP_DEFAULT_HOST = 'localhost'

logger = logging.getLogger(__name__)


class MessageQueue(object):

    def __init__(self, exchange, queue_name, routing_key):
        fr = open('./config/config.yml', 'r')
        config = yaml.load(fr)
        port = config['amqp']['port']
        host = config['amqp']['host']
        self.exchange = exchange
        self.queue_name = queue_name
        self.routing_key = routing_key
        self.port = port or AMQP_DEFAULT_PORT
        self.host = host or AMQP_DEFAULT_HOST
        self.parameters = pika.ConnectionParameters(host=self.host, port=self.port)
        self.on_close = lambda failure: None
        self.on_ready = lambda channel: None

    def _connect(self):
        cc = protocol.ClientCreator(reactor, TwistedProtocolConnection, self.parameters)
        d = retry(5, 4, cc.connectTCP, self.host, self.port)
        d.addCallback(lambda p: p.ready)
        d.addCallback(self._on_connect)

    @defer.inlineCallbacks
    def _on_connect(self, connection):
        logger.info('Connected to %s:%s' % (self.parameters.host, self.parameters.port))
        d = defer.Deferred()
        d.addErrback(self._on_close)
        connection.ready = d

        self.channel = yield connection.channel()
        yield self.channel.exchange_declare(self.exchange, 'direct')
        queue = yield self.channel.queue_declare(queue=self.queue_name)
        yield self.channel.queue_bind(self.queue_name, self.exchange, self.routing_key)
        yield self._on_ready(self.channel)

    def _on_close(self, failure):
        return self.on_close(failure)

    def _on_ready(self, channel):
        return self.on_ready(channel)

    @defer.inlineCallbacks
    def consume(self, callback):

        @defer.inlineCallbacks
        def read(queue_object):
            ch, method, properties, body = yield queue_object.get()
            yield callback(body)
            yield ch.basic_ack(delivery_tag=method.delivery_tag)

        yield self.channel.basic_qos(prefetch_count=1)
        queue_object, consumer_tag = yield self.channel.basic_consume(
                queue=self.queue_name, no_ack=False)
        l = task.LoopingCall(read, queue_object)
        l.start(0.01)

        logger.info('Start consuming')

    def publish(self, message):
        parcel = json.dumps(message).encode('utf-8')
        return self.channel.basic_publish(
            exchange=self.exchange,
            routing_key=self.routing_key,
            body=parcel)


def retry(times, sleep, func, *args, **kwargs):
    """retry a defer function
    @param times: how many times to retry
    @param sleep: seconds to sleep before retry
    @param func: defer function
    See: http://blog.ez2learn.com/2009/09/26/an-auto-retry-recipe-for-twisted/
    """
    errorList = []
    deferred = defer.Deferred()

    def run():
        logger.info('Try %s(*%s, **%s)', func.__name__, args, kwargs)
        d = func(*args, **kwargs)
        d.addCallbacks(deferred.callback, error)

    def error(error):
        errorList.append(error)
        # Retry
        if len(errorList) < times:
            logger.warn('Failed to try %s(*%s, **%s) %d times, retry...',
                    func.__name__, args, kwargs, len(errorList))
            reactor.callLater(sleep, run)
        # Fail
        else:
            logger.error('Failed to try %s(*%s, **%s) over %d times, stop',
                    func.__name__, args, kwargs, len(errorList))
            deferred.errback(errorList)
    run()
    return deferred
