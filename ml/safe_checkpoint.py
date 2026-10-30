"""Restricted legacy state reader for checksum-verified published checkpoints."""
import codecs
import collections
import pickle
import types
import numpy as np
import torch

_ALLOWED={('collections','OrderedDict'):collections.OrderedDict,
 ('torch._utils','_rebuild_tensor_v2'):torch._utils._rebuild_tensor_v2,
 ('torch','FloatStorage'):torch.FloatStorage,('torch','LongStorage'):torch.LongStorage,
 ('numpy.core.multiarray','scalar'):np.core.multiarray.scalar,
 ('numpy','dtype'):np.dtype,('_codecs','encode'):codecs.encode}

class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self,module,name):
        if (module,name) not in _ALLOWED:raise pickle.UnpicklingError(f'Unsupported checkpoint global: {module}.{name}')
        return _ALLOWED[module,name]


def tensor_state(path):
    module=types.SimpleNamespace(Unpickler=RestrictedUnpickler,__name__='restricted_pickle')
    checkpoint=torch.load(path,map_location='cpu',pickle_module=module)
    state=checkpoint.get('state_dict',checkpoint)
    if not state or not all(isinstance(v,torch.Tensor) for v in state.values()):
        raise ValueError('Expected a pure tensor state dictionary')
    return state
