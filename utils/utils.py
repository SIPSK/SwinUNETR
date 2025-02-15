# Copyright 2020 - 2022 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import scipy.ndimage as ndimage
import torch
from monai import data, transforms
from utils.my_transform import *


def resample_3d(img, target_size):
    imx, imy, imz = img.shape
    tx, ty, tz = target_size
    zoom_ratio = (float(tx) / float(imx), float(ty) / float(imy), float(tz) / float(imz))
    img_resampled = ndimage.zoom(img, zoom_ratio, order=0, prefilter=False)
    return img_resampled

def resample_2d(img, target_size):
    imx, imy = img.shape
    tx, ty = target_size
    zoom_ratio = (float(tx) / float(imx), float(ty) / float(imy))
    img_resampled = ndimage.zoom(img, zoom_ratio, order=0, prefilter=False)
    return img_resampled


def dice(x, y):
    intersect = np.sum(np.sum(np.sum(x * y)))
    y_sum = np.sum(np.sum(np.sum(y)))
    if y_sum == 0:
        return 0.0
    x_sum = np.sum(np.sum(np.sum(x)))
    return 2 * intersect / (x_sum + y_sum)


class AverageMeter(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = np.where(self.count > 0, self.sum / self.count, self.sum)


def distributed_all_gather(
    tensor_list, valid_batch_size=None, out_numpy=False, world_size=None, no_barrier=False, is_valid=None
):

    if world_size is None:
        world_size = torch.distributed.get_world_size()
    if valid_batch_size is not None:
        valid_batch_size = min(valid_batch_size, world_size)
    elif is_valid is not None:
        is_valid = torch.tensor(bool(is_valid), dtype=torch.bool, device=tensor_list[0].device)
    if not no_barrier:
        torch.distributed.barrier()
    tensor_list_out = []
    with torch.no_grad():
        if is_valid is not None:
            is_valid_list = [torch.zeros_like(is_valid) for _ in range(world_size)]
            torch.distributed.all_gather(is_valid_list, is_valid)
            is_valid = [x.item() for x in is_valid_list]
        for tensor in tensor_list:
            gather_list = [torch.zeros_like(tensor) for _ in range(world_size)]
            torch.distributed.all_gather(gather_list, tensor)
            if valid_batch_size is not None:
                gather_list = gather_list[:valid_batch_size]
            elif is_valid is not None:
                gather_list = [g for g, v in zip(gather_list, is_valid_list) if v]
            if out_numpy:
                gather_list = [t.cpu().numpy() for t in gather_list]
            tensor_list_out.append(gather_list)
    return tensor_list_out

def get_transforms(args):
    if args.model_mode == "3dswin":
        train_transform = transforms.Compose(
            [
                transforms.LoadImaged(
                    keys=["image", "label", 'inklabels'], reader="NumpyReader"),
                transforms.AddChanneld(keys=["image"]),
                Copyd(keys=["label", 'inklabels'],
                    num_channel=args.num_channel, add_channel=True),
                change_channeld(keys=["image", "label", 'inklabels']),
                transforms.Orientationd(
                    keys=["image", "label", 'inklabels'], axcodes="RAS"),
                transforms.Spacingd(
                    keys=["image", "label", 'inklabels'], pixdim=(args.space_x, args.space_y, args.space_z), mode=("bilinear", "nearest", "nearest")
                ),
                transforms.ScaleIntensityRanged(
                    keys=["image"], a_min=args.a_min, a_max=args.a_max, b_min=args.b_min, b_max=args.b_max, clip=True
                ),
                Drop1Layerd(keys=["image", "label", 'inklabels']),
                printShaped(keys=["image", "label", 'inklabels']),
                transforms.CropForegroundd(
                    keys=["image", "label", 'inklabels'], source_key="image"),
                transforms.RandCropByPosNegLabeld(
                    keys=["image", "label", 'inklabels'],
                    label_key="inklabels",
                    spatial_size=(args.roi_x, args.roi_y, args.roi_z),
                    pos=1,
                    neg=1,
                    num_samples=8,
                    image_key="image",
                    image_threshold=0,
                    allow_smaller=False,
                ),

                transforms.RandFlipd(
                    keys=["image", 'inklabels'], prob=args.RandFlipd_prob, spatial_axis=0),
                transforms.RandFlipd(
                    keys=["image", 'inklabels'], prob=args.RandFlipd_prob, spatial_axis=1),
                transforms.RandFlipd(
                    keys=["image", 'inklabels'], prob=args.RandFlipd_prob, spatial_axis=2),
                transforms.RandRotate90d(
                    keys=["image", 'inklabels'], prob=args.RandRotate90d_prob, max_k=3),
                transforms.RandScaleIntensityd(
                    keys="image", factors=0.1, prob=args.RandScaleIntensityd_prob),
                transforms.RandShiftIntensityd(
                    keys="image", offsets=0.1, prob=args.RandShiftIntensityd_prob),
                transforms.ToTensord(keys=["image", 'inklabels']),
            ]
        )
        val_transform = transforms.Compose(
            [
                transforms.LoadImaged(
                    keys=["image", "label", 'inklabels'], reader="NumpyReader"),
                Copyd(keys=["label", 'inklabels'], num_channel=65),
                # transforms.GridSplitd(keys=["image", 'inklabels'], grid=(10,10)),
                transforms.AddChanneld(keys=["image", "label", 'inklabels']),
                transforms.Orientationd(
                    keys=["image", "label", 'inklabels'], axcodes="RAS"),
                change_channeld(keys=["image", "label", 'inklabels']),
                Drop1Layerd(keys=["image", "label", 'inklabels']),
                transforms.Spacingd(
                    keys=["image", "label", 'inklabels'], pixdim=(args.space_x, args.space_y, args.space_z), mode=("bilinear", "nearest", "nearest")
                ),
                transforms.ScaleIntensityRanged(
                    keys=["image"], a_min=args.a_min, a_max=args.a_max, b_min=args.b_min, b_max=args.b_max, clip=True
                ),
                transforms.CropForegroundd(
                    keys=["image", "label", 'inklabels'], source_key="image"),
                transforms.ToTensord(keys=["image", 'inklabels']),
            ]
        )
        test_transform = transforms.Compose(
        [
            transforms.LoadImaged(
                keys=["image", "label"], reader="NumpyReader"),
            transforms.AddChanneld(keys=["image"]),
            Copyd(keys=["label", 'inklabels'], num_channel=args.num_channel),
            # transforms.Orientationd(keys=["image"], axcodes="RAS"),
            change_channeld(keys=["image", "label", 'inklabels']),
            transforms.Spacingd(keys="image", pixdim=(
                args.space_x, args.space_y, args.space_z), mode="bilinear"),
            transforms.ScaleIntensityRanged(
                keys=["image"], a_min=args.a_min, a_max=args.a_max, b_min=args.b_min, b_max=args.b_max, clip=True
            ),
            transforms.ToTensord(keys=["image"]),
        ]
    )
    elif args.model_mode == "2dswin":
        train_transform = transforms.Compose(
            [
                transforms.LoadImaged(
                    keys=["image", "label", 'inklabels'], reader="NumpyReader"),
                transforms.AddChanneld(keys=["image"]),
                Copyd(keys=["label", 'inklabels'],
                      num_channel=args.num_channel, add_channel=True),
                change_channeld(keys=["image", "label", 'inklabels']),
                transforms.Orientationd(
                    keys=["image", "label", 'inklabels'], axcodes="RAS"),
                # transforms.Spacingd(
                #     keys=["image", "label", 'inklabels'], pixdim=(args.space_x, args.space_y, args.space_z), mode=("bilinear", "nearest", "nearest")
                # ),
                transforms.ScaleIntensityRanged(
                    keys=["image"], a_min=args.a_min, a_max=args.a_max, b_min=args.b_min, b_max=args.b_max, clip=True
                ),
                # Drop1Layerd(keys=["image", "label", 'inklabels']),
                # transforms.CropForegroundd(keys=["image", "label", 'inklabels'], source_key="image"),
                # printShaped(keys=["image", "label", 'inklabels']),
                transforms.RandCropByPosNegLabeld(
                    keys=["image", "label", 'inklabels'],
                    label_key="inklabels",
                    spatial_size=(args.roi_x, args.roi_y, args.roi_z),
                    pos=1,
                    neg=1,
                    num_samples=32,
                    image_key="image",
                    image_threshold=0,
                    allow_smaller=False,
                ),
                # printShaped(keys=["image", "label", 'inklabels']),
                transforms.RandFlipd(
                    keys=["image", 'inklabels'], prob=args.RandFlipd_prob, spatial_axis=0),
                transforms.RandFlipd(
                    keys=["image", 'inklabels'], prob=args.RandFlipd_prob, spatial_axis=1),
                transforms.RandFlipd(
                    keys=["image", 'inklabels'], prob=args.RandFlipd_prob, spatial_axis=2),
                transforms.RandRotate90d(
                    keys=["image", 'inklabels'], prob=args.RandRotate90d_prob, max_k=3),
                transforms.RandScaleIntensityd(
                    keys="image", factors=0.1, prob=args.RandScaleIntensityd_prob),
                transforms.RandShiftIntensityd(
                    keys="image", offsets=0.1, prob=args.RandShiftIntensityd_prob),
                change_channeld(
                    keys=["image", "label", 'inklabels'], back=True),
                # printShaped(keys=["image", "label", 'inklabels']),
                remove_channeld(keys=["image", "label", 'inklabels']),
                transforms.ToTensord(keys=["image", 'inklabels']),
            ]
        )
        val_transform = transforms.Compose(
            [
                transforms.LoadImaged(
                    keys=["image", "label", 'inklabels'], reader="NumpyReader"),
                Copyd(keys=["label", 'inklabels'],
                      num_channel=args.num_channel),
                # transforms.GridSplitd(keys=["image", 'inklabels'], grid=(10,10)),
                transforms.AddChanneld(keys=["image", "label", 'inklabels']),
                transforms.Orientationd(
                    keys=["image", "label", 'inklabels'], axcodes="RAS"),
                change_channeld(keys=["image", "label", 'inklabels']),
                # Drop1Layerd(keys=["image", "label", 'inklabels']),
                # transforms.Spacingd(
                #     keys=["image", "label", 'inklabels'], pixdim=(args.space_x, args.space_y, args.space_z), mode=("bilinear", "nearest", "nearest")
                # ),
                transforms.ScaleIntensityRanged(
                    keys=["image"], a_min=args.a_min, a_max=args.a_max, b_min=args.b_min, b_max=args.b_max, clip=True
                ),
                transforms.CropForegroundd(
                    keys=["image", "label", 'inklabels'], source_key="image"),
                change_channeld(
                    keys=["image", "label", 'inklabels'], back=True),
                remove_channeld(keys=["image", "label", 'inklabels']),
                transforms.ToTensord(keys=["image", 'inklabels']),
            ]
        )
        test_transform = transforms.Compose(
            [
                transforms.LoadImaged(
                    keys=["image", "label"], reader="NumpyReader"),
                # transforms.AddChanneld(keys=["image"]),
                Copyd(keys=["label", 'inklabels'],
                      num_channel=args.num_channel),
                # transforms.Orientationd(keys=["image"], axcodes="RAS"),
                # change_channeld(keys=["image", "label", 'inklabels']),
                # transforms.Spacingd(keys="image", pixdim=(args.space_x, args.space_y, args.space_z), mode="bilinear"),
                transforms.ScaleIntensityRanged(
                    keys=["image"], a_min=args.a_min, a_max=args.a_max, b_min=args.b_min, b_max=args.b_max, clip=True
                ),
                transforms.ToTensord(keys=["image"]),
            ]
        )
    else:
        raise ValueError("model_mode should be ['3dswin', '2dswin', '3dunet', '2dunet']")
    return train_transform, val_transform, test_transform