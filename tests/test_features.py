"""Observable feature contracts; all evidence metadata is invented."""

import math

import numpy as np
import pytest

from outcome_poc.features import build_features, feature_schema
from outcome_poc.schemas import RankedDocument
from outcome_poc.storage import content_hash


def packet(scores=(.9, .8, .6, .55, .5, .45, .4, .3, .2, .1)):
    return [RankedDocument(f'd{i}', float(score), i, (i+1)*10, 2, 'Invented')
            for i, score in enumerate(scores)]


def test_all_42_positions_use_observable_metadata_and_population_summaries():
    values = build_features('Who glows?', packet())
    expected = [math.log1p(10), math.log1p(2), 0, 0, 0, 1, 0,
                .9, .8, .6, .55, .5, .45, .4, .3, .2, .1,
                .1, .2, .05, .05, .05, .05, .1, .1, .1,
                .48, .23685438564654024, .937553826696166,
                math.log1p(30), math.log1p(550), 10] + [1]*10
    assert values.shape == (42,)
    assert values.dtype == np.float64
    np.testing.assert_allclose(values, expected, rtol=1e-13, atol=1e-13)


@pytest.mark.parametrize('question,pattern', [
    ('  IS  who number of what year?', 0), ('Islander glows?', 4),
    ('When is number of?', 1), ('Ask which year number of?', 1),
    ('What yearly glow?', 4), ('How many lanterns?', 2),
    ('WHO has a number of lanterns?', 2), ('Who glows?', 3), ('Whom glows?', 4),
])
def test_patterns_have_word_boundaries_and_ordered_exclusive_precedence(question, pattern):
    assert build_features(question, packet())[2:7].tolist() == [int(i == pattern) for i in range(5)]


def test_short_packet_pads_minimum_and_only_real_neighbor_gaps():
    values = build_features('é  lamp?', packet((.5, .25)))
    np.testing.assert_allclose(values[7:17], [.5] + [.25]*9)
    np.testing.assert_allclose(values[17:26], [.25] + [0]*8)
    np.testing.assert_allclose(values[26:28], [.275, .075])
    assert values[29:32].tolist() == [math.log1p(30), math.log1p(30), 2]
    assert values[32:].tolist() == [1, 1] + [0]*8
    assert values[0] == math.log1p(8)
    assert values[1] == math.log1p(2)


def test_float64_entropy_is_stable_for_extreme_finite_scores():
    values = build_features('Lamp?', packet((1e200, -1e200)))
    assert values[28] == 0
    assert np.isfinite(values).all()


def test_feature_schema_is_canonical_and_returned_without_shared_mutation():
    schema = feature_schema()
    assert schema['version'] == 'features_v1'
    assert len(schema['features']) == 42
    assert schema['dtype'] == 'float64'
    digest = schema.pop('hash')
    assert digest == content_hash(schema)
    schema['features'].clear()
    assert len(feature_schema()['features']) == 42


@pytest.mark.parametrize('ranked', [[], packet((float('nan'),)), packet(tuple(range(11))),
                                   list(reversed(packet((.5, .25))))])
def test_invalid_or_empty_ranking_refuses_feature_construction(ranked):
    with pytest.raises(ValueError):
        build_features('Lamp?', ranked)
