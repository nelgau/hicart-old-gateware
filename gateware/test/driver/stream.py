from nmigen.sim import *


class StreamDriver:

    def __init__(self, stream):
        self.stream = stream

    def begin(self):
        yield

    def produce(self, item):
        yield from self.produce_many([item])

    def produce_many(self, items):
        for item in items:
            yield self.stream.payload.eq(item)
            yield self.stream.valid.eq(1)
            yield Settle()

            waited = False

            while not (yield self.stream.ready):
                waited = True
                yield

            if not waited:
                yield

        yield self.stream.payload.eq(0)
        yield self.stream.valid.eq(0)
        yield

    def consume(self):
        return (yield from self.consume_many(1))[0]

    def consume_many(self, count):
        results = []

        yield self.stream.ready.eq(1)
        yield Settle()

        while len(results) < count:
            waited = False

            while not (yield self.stream.valid):
                waited = True
                yield

            results.append((yield self.stream.payload))

            if not waited:
                yield

        yield self.stream.ready.eq(0)
        yield

        return results
