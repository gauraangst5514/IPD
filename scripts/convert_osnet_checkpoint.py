"""Convert known first-party legacy checkpoint with a narrow pickle allowlist."""
import sys,pathlib,pickle,types,collections,codecs
import numpy as np
import torch
ROOT=pathlib.Path(__file__).resolve().parents[1]
allowed={('collections','OrderedDict'):collections.OrderedDict,
 ('torch._utils','_rebuild_tensor_v2'):torch._utils._rebuild_tensor_v2,
 ('torch','FloatStorage'):torch.FloatStorage,('torch','LongStorage'):torch.LongStorage,
 ('numpy.core.multiarray','scalar'):np.core.multiarray.scalar,
 ('numpy','dtype'):np.dtype,('_codecs','encode'):codecs.encode}
class Restricted(pickle.Unpickler):
 def find_class(self,module,name):
  if (module,name) not in allowed:raise pickle.UnpicklingError(f'Unsupported global: {module}.{name}')
  return allowed[module,name]
source=ROOT/'data/raw/generali/extracted/model_similarity_best/osnet_sim_v2.tar'
module=types.SimpleNamespace(Unpickler=Restricted,__name__='restricted_pickle')
checkpoint=torch.load(source,map_location='cpu',pickle_module=module)
print('Top-level keys',list(checkpoint)[:12])
state=checkpoint.get('state_dict',checkpoint)
state={k.removeprefix('module.'):v for k,v in state.items() if isinstance(v,torch.Tensor)}
if not state:raise ValueError('No tensor state found')
target=ROOT/'ml/weights/osnet_similarity_state.pt';torch.save(state,target)
print('Saved',target,'tensors',len(state));print([(k,tuple(v.shape)) for k,v in state.items()][-8:])
