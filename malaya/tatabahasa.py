from malaya.supervised import t5 as t5_load
from malaya.supervised import transformer as load_transformer
from malaya.model.tf import Tatabahasa
from malaya.model.t5 import Tatabahasa as T5_Tatabahasa
from herpetologist import check_type

_transformer_tagging_availability = {
    'small': {
        'Size (MB)': 397,
        'Quantized Size (MB)': 100,
        'Sequence Accuracy': 0.860198,
        'Sequence Tagging Accuracy': 0.96326745,
    },
    'base': {
        'Size (MB)': 875,
        'Quantized Size (MB)': 220,
        'Sequence Accuracy': 0.938972,
        'Sequence Tagging Accuracy': 0.977407,
    },
}

_transformer_availability = {
    't5': {
        'Size (MB)': 1250,
        'Quantized Size (MB)': 481,
        'WER': 0.0178902,
    },
    'small-t5': {
        'Size (MB)': 355.6,
        'Quantized Size (MB)': 195,
        'WER': 0.0187973,
    },
    'tiny-t5': {
        'Size (MB)': 208,
        'Quantized Size (MB)': 103,
        'WER': 0.0328037,
    },
    'super-tiny-t5': {
        'Size (MB)': 81.8,
        'Quantized Size (MB)': 27.1,
        'WER': 0.0351141,
    },
    '3x-super-tiny-t5': {
        'Size (MB)': 18.3,
        'Quantized Size (MB)': 4.46,
        'WER': 0.03676189,
    },
}


def describe_tagging():
    """
    Describe kesalahan tatabahasa supported.
    Full description at https://tatabahasabm.tripod.com/tata/salahtata.htm
    """
    d = [{'class': 0,
          'Description': 'PAD',
          'salah': '',
          'betul': ''},
         {'class': 1,
          'Description': 'kesambungan subwords',
          'salah': '',
          'betul': '',
          },
         {'class': 2,
         'Description': 'tiada kesalahan',
          'salah': '',
          'betul': '',
          },
         {'class': 3,
         'Description': 'kesalahan frasa nama, Perkara yang diterangkan mesti mendahului "penerang"',
          'salah': 'Cili sos',
          'betul': 'sos cili',
          },
         {'class': 4,
         'Description': 'kesalahan kata jamak',
          'salah': 'mereka-mereka',
          'betul': 'mereka',
          },
         {'class': 5,
         'Description': 'kesalahan kata penguat',
          'salah': 'sangat tinggi sekali',
          'betul': 'sangat tinggi',
          },
         {'class': 6,
         'Description': 'kata adjektif dan imbuhan "ter" tanpa penguat.',
          'salah': 'Sani mendapat markah yang tertinggi sekali.',
          'betul': 'Sani mendapat markah yang tertinggi.',
          },
         {'class': 7,
         'Description': 'kesalahan kata hubung',
          'salah': 'Sally sedang membaca bila saya tiba di rumahnya.',
          'betul': 'Sally sedang membaca apabila saya tiba di rumahnya.',
          },
         {'class': 8,
         'Description': 'kesalahan kata bilangan',
          'salah': 'Beribu peniaga tidak membayar cukai pendapatan.',
          'betul': 'Beribu-ribu peniaga tidak membayar cukai pendapatan',
          },
         {'class': 9,
         'Description': 'kesalahan kata sendi',
          'salah': 'Umar telah berpindah daripada sekolah ini bulan lalu.',
          'betul': 'Umar telah berpindah dari sekolah ini bulan lalu.',
          },
         {'class': 10,
         'Description': 'kesalahan penjodoh bilangan',
          'salah': 'Setiap orang pelajar',
          'betul': 'Setiap pelajar.',
          },
         {'class': 11,
         'Description': 'kesalahan kata ganti diri',
          'salah': 'Pencuri itu telah ditangkap. Beliau dibawa ke balai polis.',
          'betul': 'Pencuri itu telah ditangkap. Dia dibawa ke balai polis.',
          },
         {'class': 12,
         'Description': 'kesalahan ayat pasif',
          'salah': 'Cerpen itu telah dikarang oleh saya.',
          'betul': 'Cerpen itu telah saya karang.',
          },
         {'class': 13,
         'Description': 'kesalahan kata tanya',
          'salah': 'Kamu berasal dari manakah ?',
          'betul': 'Kamu berasal dari mana ?',
          },
         {'class': 14,
         'Description': 'kesalahan tanda baca',
          'salah': 'Kamu berasal dari manakah .',
          'betul': 'Kamu berasal dari mana ?',
          },
         {'class': 15,
         'Description': 'kesalahan kata kerja tak transitif',
          'salah': 'Dia kata kepada saya',
          'betul': 'Dia berkata kepada saya',
          },
         {'class': 16,
         'Description': 'kesalahan kata kerja transitif',
          'salah': 'Dia suka baca buku',
          'betul': 'Dia suka membaca buku',
          },
         {'class': 17,
         'Description': 'penggunaan kata yang tidak tepat',
          'salah': 'Tembuk Besar negeri Cina dibina oleh Shih Huang Ti.',
          'betul': 'Tembok Besar negeri Cina dibina oleh Shih Huang Ti',
          },
         ]

    from malaya.function import describe_availability

    return describe_availability(d, transpose=False)


def available_transformer_tagging():
    """
    List available transformer tagging models.
    """
    from malaya.function import describe_availability

    return describe_availability(
        _transformer_tagging_availability,
        text='tested on 10k kesalahan tatabahasa texts.',
    )


def available_transformer():
    """
    List available transformer models.
    """
    from malaya.function import describe_availability

    return describe_availability(
        _transformer_availability,
        text='tested on 7.5k kesalahan tatabahasa texts.',
    )


@ check_type
def transformer(model: str = 'small-t5', quantized: bool = False, **kwargs):
    """
    Load Malaya transformer encoder-decoder model to correct a `kesalahan tatabahasa` text.

    Parameters
    ----------
    model : str, optional (default='small-t5')
        Model architecture supported. Allowed values:

        * ``'t5'`` - T5 BASE parameters.
        * ``'small-t5'`` - T5 SMALL parameters.
        * ``'tiny-t5'`` - T5 TINY parameters.
        * ``'super-tiny-t5'`` - T5 SUPER TINY parameters.
        * ``'3x-super-tiny-t5'`` - T5 3X SUPER TINY parameters.

    quantized : bool, optional (default=False)
        if True, will load 8-bit quantized model.
        Quantized model not necessary faster, totally depends on the machine.

    Returns
    -------
    result: model
        List of model classes:

        * if `t5` in model, will return `malaya.model.t5.Tatabahasa`.
    """

    model = model.lower()
    if model not in _transformer_availability:
        raise ValueError(
            'model not supported, please check supported models from `malaya.tatabahasa.available_transformer()`.'
        )
    return t5_load.load(
        module='kesalahan-tatabahasa',
        model=model,
        model_class=T5_Tatabahasa,
        quantized=quantized,
        **kwargs,
    )


@check_type
def transformer_tagging(model: str = 'base', quantized: bool = False, **kwargs):
    """
    Load Malaya transformer encoder-decoder + tagging model to correct a `kesalahan tatabahasa` text.

    Parameters
    ----------
    model : str, optional (default='base')
        Model architecture supported. Allowed values:

        * ``'small'`` - Malaya Transformer Tag SMALL parameters.
        * ``'base'`` - Malaya Transformer Tag BASE parameters.

    quantized : bool, optional (default=False)
        if True, will load 8-bit quantized model.
        Quantized model not necessary faster, totally depends on the machine.

    Returns
    -------
    result: malaya.model.tf.Tatabahasa class
    """

    model = model.lower()
    if model not in _transformer_tagging_availability:
        raise ValueError(
            'model not supported, please check supported models from `malaya.tatabahasa.available_transformer_tagging()`.'
        )

    return load_transformer.load_tatabahasa(
        module='kesalahan-tatabahasa',
        model=model,
        model_class=Tatabahasa,
        quantized=quantized,
        **kwargs
    )
