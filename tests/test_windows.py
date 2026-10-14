import pytest
from outcome_poc import retrieval
from retrieval_helpers import Tokenizer, document


def test_overlong_sentence_keeps_original_identity_and_complete_token_spans():
    doc = document('Title', [' '.join(['word'] * 1000)])
    windows = retrieval.embedding_windows(doc, Tokenizer())
    assert [w['token_count'] for w in windows] == [480, 480, 49]
    assert [w['spans'][0]['sentence_index'] for w in windows] == [0, 0, 0]
    assert [(w['spans'][0]['token_start'], w['spans'][0]['token_end']) for w in windows] == [(0, 477), (477, 954), (954, 1000)]
    assert all(w['text'].startswith('Title\n') for w in windows)


def test_whole_consecutive_sentences_pack_with_original_text_and_no_prefix():
    windows = retrieval.embedding_windows(document('Title', ['one two', 'three four', 'five six']), Tokenizer(), 7)
    assert [w['text'] for w in windows] == ['Title\none two\nthree four', 'Title\nfive six']
    assert [[s['sentence_index'] for s in w['spans']] for w in windows] == [[0, 1], [2]]


def test_title_overhead_that_leaves_no_body_capacity_fails_visibly():
    with pytest.raises(ValueError, match='title'):
        retrieval.embedding_windows(document('one two three', ['body']), Tokenizer(), 5)


def test_fragment_reencoding_is_recounted_instead_of_assuming_token_slice_identity():
    class Pieces(Tokenizer):
        def __call__(self, text, **kwargs):
            # abcdef has two original pieces; fragment def expands into three.
            value = super().__call__(text, **kwargs)
            if text == 'abcdef':
                return {'input_ids': [10, 11], 'offset_mapping': [(0, 3), (3, 6)]}
            if text.endswith('def'):
                ids = value['input_ids']
                value['input_ids'] = ids[:-1] + [20, 21] + ids[-1:] if kwargs.get('add_special_tokens', True) else ids + [20, 21]
            return value
    with pytest.raises(ValueError, match='fragment'):
        retrieval.embedding_windows(document('Title', ['abcdef']), Pieces(), 4)
