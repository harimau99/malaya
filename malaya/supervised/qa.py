from malaya.function import (
    check_file,
    load_graph,
    generate_session,
    nodes_session,
)
from malaya.text.bpe import (
    sentencepiece_tokenizer_bert,
    sentencepiece_tokenizer_xlnet,
    AlbertTokenizer,
)
from malaya.model.tf import SQUAD
from malaya.path import MODEL_VOCAB, MODEL_BPE

LENGTHS = {'bert': 384, 'xlnet': 512}


def transformer_squad(class_name, model='bert', quantized=False, **kwargs):
    path = check_file(
        file=model,
        module=class_name,
        keys={
            'model': 'model.pb',
            'vocab': MODEL_VOCAB[model],
            'tokenizer': MODEL_BPE[model],
        },
        quantized=quantized,
        **kwargs,
    )

    g = load_graph(path['model'], **kwargs)
    inputs = ['Placeholder', 'Placeholder_1', 'Placeholder_2', 'Placeholder_3']

    if model in ['bert', 'tiny-bert']:
        tokenizer = sentencepiece_tokenizer_bert(
            path['tokenizer'], path['vocab']
        )
    if model in ['albert', 'tiny-albert']:
        tokenizer = AlbertTokenizer(
            vocab_file=path['vocab'], spm_model_file=path['tokenizer']
        )
    if model in ['xlnet', 'alxlnet']:
        tokenizer = sentencepiece_tokenizer_xlnet(path['tokenizer'])
        inputs.append('Placeholder_4')

    outputs = [
        'start_top_log_probs',
        'start_top_index',
        'end_top_log_probs',
        'end_top_index',
        'cls_logits',
        'logits_vectorize',
    ]
    input_nodes, output_nodes = nodes_session(g, inputs, outputs)

    mode = 'bert' if 'bert' in model else 'xlnet'
    return SQUAD(
        input_nodes=input_nodes,
        output_nodes=output_nodes,
        sess=generate_session(graph=g, **kwargs),
        tokenizer=tokenizer,
        class_name=class_name,
        mode=mode,
        length=LENGTHS[mode],
    )
