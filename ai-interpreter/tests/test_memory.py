"""Memory stays bounded on the CPU path CI can actually run.

The GPU model is not installed in this job. These checks cover the heuristic
adapter the pipeline uses until a fine-tuned adapter exists.
"""

import gc
import tracemalloc

import pytest

from app.services.interpreter import HeuristicInterpreter
from tests.test_api import cervix_image

pytestmark = pytest.mark.memory


def test_repeated_reads_release_their_allocations():
    image = cervix_image(True)
    engine = HeuristicInterpreter()
    engine.interpret(image, {}, [])
    gc.collect()
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]
    for _ in range(25):
        engine.interpret(image, {}, [])
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert current - baseline < 2_000_000
    assert peak < 40_000_000


def test_one_read_stays_under_the_cpu_budget():
    image = cervix_image(True)
    tracemalloc.start()
    HeuristicInterpreter().interpret(image, {}, [])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 20_000_000
