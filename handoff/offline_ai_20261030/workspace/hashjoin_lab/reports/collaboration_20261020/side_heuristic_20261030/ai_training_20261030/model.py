"""General causal plan ranker and masked, case-balanced supervision."""
import torch
from torch import nn
from torch.nn import functional as F


def ranking_loss(scores, targets, valid, observable, weights):
    """Missing candidates and unlearnable identical-input pairs are masked.

    Pair supervision retains normalized cost-gap magnitude. Callers give
    all-cost-tie rows zero case weight.
    """
    valid = valid.bool()
    if not torch.isfinite(targets[valid]).all():
        raise ValueError('nonfinite valid target')
    safe_scores = torch.where(valid, scores, torch.zeros_like(scores))
    safe_targets = torch.where(valid, targets, torch.zeros_like(targets))
    value = (F.smooth_l1_loss(safe_scores, safe_targets, reduction='none') * valid).sum(1)
    value = value / valid.sum(1).clamp_min(1)
    diff = safe_targets[:, :, None] - safe_targets[:, None, :]
    pair = valid[:, :, None] & valid[:, None, :]
    pair = pair & (diff.abs() > 0) & torch.ones_like(pair).triu(1)
    same = (observable[:, :, None, :] == observable[:, None, :, :]).all(-1)
    pair = pair & ~same
    ds = safe_scores[:, :, None] - safe_scores[:, None, :]
    element = F.softplus(-ds * diff.sign() / 0.25) * diff.abs()
    ranking = (element * pair).sum((1, 2)) / pair.sum((1, 2)).clamp_min(1)
    return ((value + 0.25 * ranking) * weights).sum()


class PlanRanker(nn.Module):
    def __init__(self, hidden, zero_columns=(), base_skip=True):
        super().__init__()
        self.hidden = list(hidden)
        self.zero_columns = list(zero_columns)
        self.base_skip = bool(base_skip)
        dims = [32] + self.hidden + [1]
        self.layers = nn.ModuleList(nn.Linear(a, b) for a, b in zip(dims, dims[1:]))
        mask = torch.ones(32)
        mask[self.zero_columns] = 0
        self.register_buffer('input_mask', mask)
        nn.init.zeros_(self.layers[-1].weight)
        nn.init.zeros_(self.layers[-1].bias)

    def observable(self, x):
        masked = x * self.input_mask
        return torch.cat((masked, x[..., 13:14]), -1) if self.base_skip else masked

    def forward(self, x):
        h = x * self.input_mask
        for layer in self.layers[:-1]:
            h = F.relu(layer(h))
        residual = self.layers[-1](h).squeeze(-1).clamp(-1, 1)
        return residual + x[..., 13] if self.base_skip else residual

    def export(self):
        return {'feature_dim': 32, 'hidden': self.hidden,
                'zero_columns': self.zero_columns, 'base_skip': self.base_skip,
                'layers': [{'weight': l.weight.detach().cpu().tolist(),
                            'bias': l.bias.detach().cpu().tolist()} for l in self.layers],
                'parameters': sum(p.numel() for p in self.parameters()),
                'macs_per_plan': sum(l.in_features * l.out_features for l in self.layers)}
