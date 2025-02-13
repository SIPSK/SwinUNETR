import torch.nn as nn
import torch.nn.functional as F
from monai.losses import GeneralizedDiceLoss

class CustomWeightedCELoss(nn.Module):
    def __init__(self, ink_weight=10.0, background_weight=1.0):
        super(CustomWeightedCELoss, self).__init__()
        self.ink_weight = ink_weight
        self.background_weight = background_weight

    def forward(self, logits, labels):
        weights = labels * (self.ink_weight - self.background_weight) + self.background_weight
        ce_loss = F.binary_cross_entropy_with_logits(logits, labels, weight=weights, reduction='mean')
        return ce_loss

class CustomWeightedDiceCELoss(nn.Module):
    def __init__(self, ink_weight=10.0, background_weight=1.0):
        super(CustomWeightedDiceCELoss, self).__init__()
        self.ce_loss = CustomWeightedCELoss(ink_weight, background_weight)
        self.dice_loss = GeneralizedDiceLoss(include_background=True, to_onehot_y=False, softmax=False)

    def forward(self, logits, labels):
        ce_loss_value = self.ce_loss(logits, labels)
        dice_loss_value = self.dice_loss(logits, labels)
        total_loss = ce_loss_value + dice_loss_value
        return total_loss