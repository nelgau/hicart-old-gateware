import itertools

from nmigen import *
from nmigen.build import *


def get_all_resources(platform, name):
    resources = []
    for number in itertools.count():
        try:
            resources.append(platform.request(name, number))
        except ResourceError:
            break
    return resources
