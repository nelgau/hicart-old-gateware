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

            did_advance = False

            while not (yield self.stream.ready):
                did_advance = True
                yield

            if not did_advance:
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
            did_advance = False

            while not (yield self.stream.valid):
                did_advance = True
                yield

            results.append((yield self.stream.payload))

            if not did_advance:
                yield

        yield self.stream.ready.eq(0)
        yield

        return results
