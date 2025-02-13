from monai.transforms.transform import Transform
from monai.transforms.transform import MapTransform
from monai.config import KeysCollection
from typing import Dict, Hashable, Mapping
from monai.config.type_definitions import NdarrayOrTensor
import torch

class remove_channel(Transform):
    def __init__(self):
        pass
    
    def __call__(self, data):
        if isinstance(data, torch.Tensor):
            if len(data.shape) == 4:
                ret = data[0, :, :, :]
            elif len(data.shape) ==  5:
                ret = data[:, 0, :, :, :]
            elif len(data.shape) == 3:
                ret = data
            else:
                raise ValueError(f"Input size: {data.shape} cannot handle")
        return ret
    
class remove_channeld(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.AddChannel`.
    """
    def __init__(self, keys: KeysCollection) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            allow_missing_keys: don't raise exception if key is missing.
        """
        super().__init__(keys, )
        self.adder = remove_channel()
        pass
    
    def __call__(self, data: Mapping[Hashable, NdarrayOrTensor]) -> Dict[Hashable, NdarrayOrTensor]:
        d = dict(data)
        for key in self.key_iterator(d):
            d[key] = self.adder(d[key])
        return d
    
class change_channel(Transform):
    def __init__(self, back=False):
        self.back = back
        pass
    
    def __call__(self, data):
        if isinstance(data, torch.Tensor):
            if not self.back:
                data = data.permute(0, 2, 3, 1)
            else: 
                data = data.permute(0, 3, 1, 2)
        return data
    
class change_channeld(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.AddChannel`.
    """
    def __init__(self, keys: KeysCollection, back=False) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            allow_missing_keys: don't raise exception if key is missing.
        """
        super().__init__(keys, )
        self.adder = change_channel(back=back)
        pass
    
    def __call__(self, data: Mapping[Hashable, NdarrayOrTensor]) -> Dict[Hashable, NdarrayOrTensor]:
        d = dict(data)
        for key in self.key_iterator(d):
            d[key] = self.adder(d[key])
        return d
    
class printShape(Transform):
    def __init__(self):
        pass
    
    def __call__(self, data):
        print(data.shape)
        return data
    
class printShaped(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.AddChannel`.
    """
    def __init__(self, keys: KeysCollection) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            allow_missing_keys: don't raise exception if key is missing.
        """
        super().__init__(keys, )
        pass
    
    def __call__(self, data: Mapping[Hashable, NdarrayOrTensor]) -> Dict[Hashable, NdarrayOrTensor]:
        d = dict(data)
        for key in self.key_iterator(d):
            print(d[key].shape)
        return d
    
class Drop1Layer(Transform):
    def __init__(self):
        pass
    
    def __call__(self, data):
        data_shape = data.shape
        if len(data_shape) == 3:
            _,_,z = data_shape
            ret = data[:, :, :z-1]
        elif len(data_shape) == 4:
            _,_,_,z = data_shape
            ret = data[:, :, :, :z-1]
        else:
            raise Exception("Input demention error")
        return ret
    
class Drop1Layerd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.AddChannel`.
    """
    def __init__(self, keys: KeysCollection) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            allow_missing_keys: don't raise exception if key is missing.
        """
        super().__init__(keys, )
        self.adder = Drop1Layer()

    def __call__(self, data: Mapping[Hashable, NdarrayOrTensor]) -> Dict[Hashable, NdarrayOrTensor]:
        d = dict(data)
        for key in self.key_iterator(d):
            d[key] = self.adder(d[key])
        return d
    
class Copy(Transform):
    def __init__(self, num_channel, add_channel=False):
        self.num_channel = num_channel
        self.add_channel = add_channel

    def __call__(self, data):
        if self.add_channel:
            data = data.repeat(1, self.num_channel, 1, 1)  # output = (batch_size=1, num_channel, H, W)
        else:
            data = data.repeat(self.num_channel, 1, 1)  # output = (batch_size=1, num_channel, H, W)
        return data
    
class Copyd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.AddChannel`.
    """
    def __init__(self, keys: KeysCollection, num_channel, add_channel=False) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            allow_missing_keys: don't raise exception if key is missing.
        """
        super().__init__(keys, )
        self.adder = Copy(num_channel, add_channel)

    def __call__(self, data: Mapping[Hashable, NdarrayOrTensor]) -> Dict[Hashable, NdarrayOrTensor]:
        d = dict(data)
        for key in self.key_iterator(d):
            d[key] = self.adder(d[key])
        return d
    

class CustomPad(Transform):
    def __init__(self, target_shape=(96, None, None)):
        self.target_shape = target_shape

    def __call__(self, data):
        if data.shape[0] == self.target_shape[0]:
            return data

        pad_size = max(0, self.target_shape[0] - data.shape[0])
        pad_size_before = pad_size // 2
        pad_size_after = pad_size - pad_size_before

        padded_data = torch.cat((torch.flip(data[:pad_size_before], dims=(0,)), 
                                 data, 
                                 torch.flip(data[-pad_size_after:], dims=(0,))), dim=0)
        return padded_data
    
class CustomPadd(MapTransform):
    """
    Dictionary-based wrapper of :py:class:`monai.transforms.AddChannel`.
    """
    def __init__(self, keys: KeysCollection) -> None:
        """
        Args:
            keys: keys of the corresponding items to be transformed.
                See also: :py:class:`monai.transforms.compose.MapTransform`
            allow_missing_keys: don't raise exception if key is missing.
        """
        super().__init__(keys, )
        self.adder = CustomPad()
        pass
    
    def __call__(self, data: Mapping[Hashable, NdarrayOrTensor]) -> Dict[Hashable, NdarrayOrTensor]:
        d = dict(data)
        for key in self.key_iterator(d):
            d[key] = self.adder(d[key])
        return d