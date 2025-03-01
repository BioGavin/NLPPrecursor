

from fastai.data import DataBunch
from fastai.core import OptStrTuple
from typing import Dict, Collection, List
from fastai.torch_core import Model, Weights, OptSplitFunc
from fastai.basic_train import Learner
from fastai.train import GradientClipping
from fastai.metrics import accuracy
from fastai.text.models import get_language_model, get_rnn_classifier
from functools import partial
from fastai.callbacks.rnn import RNNTrainer
import numpy as np
import pickle
import torch


__all__ = ['ProtRNNLearner', 'convert_weights', 'lm_split', 'rnn_classifier_split']


def convert_weights(wgts:Weights, stoi_wgts:Dict[str,int], itos_new:Collection[str]) -> Weights:
    '''Convert the model weights to go with a new vocabulary.'''
    dec_bias, enc_wgts = wgts['1.decoder.bias'], wgts['0.encoder.weight']
    bias_m, wgts_m = dec_bias.mean(0), enc_wgts.mean(0)
    new_w = enc_wgts.new_zeros((len(itos_new),enc_wgts.size(1))).zero_()
    new_b = dec_bias.new_zeros((len(itos_new),)).zero_()
    for i,w in enumerate(itos_new):
        r = stoi_wgts[w] if w in stoi_wgts else -1
        new_w[i] = enc_wgts[r] if r>=0 else wgts_m
        new_b[i] = dec_bias[r] if r>=0 else bias_m
    wgts['0.encoder.weight'] = new_w
    wgts['0.encoder_dp.emb.weight'] = new_w.clone()
    wgts['1.decoder.weight'] = new_w.clone()
    wgts['1.decoder.bias'] = new_b
    return wgts

def lm_split(model:Model) -> List[Model]:
    '''Split a RNN `model` in groups for differential learning rates.'''
    groups = [[rnn, dp] for rnn, dp in zip(model[0].rnns, model[0].hidden_dps)]
    groups.append([model[0].encoder, model[0].encoder_dp, model[1]])
    return groups


def rnn_classifier_split(model:Model) -> List[Model]:
    '''Split a RNN `model` in groups for differential learning rates.'''
    groups = [[model[0].encoder, model[0].encoder_dp]]
    groups += [[rnn, dp] for rnn, dp in zip(model[0].rnns, model[0].hidden_dps)]
    groups.append([model[1]])
    return groups

def calculate_weights(data, mode):
    if data != None:
        ary = np.array([float(data.count(i))/float(len(data)) for i in range(0, len(set(data)))])
        tensor = torch.tensor(ary, dtype=torch.float, device=mode)
        variable = torch.autograd.Variable(tensor)
        return variable
    else:
        return None

class ProtRNNLearner(Learner):
    '''Basic class for a Learner in RNN for proteins.'''
    def __init__(self, data:DataBunch, model:Model, bptt:int=70, split_func:OptSplitFunc=None, clip:float=None,
                 adjust:bool=False, alpha:float=2., beta:float=1., mode:str='CPU', labelled_data:Collection[int]=None, **kwargs):
        super().__init__(data, model)
        self.callbacks.append(RNNTrainer(self, bptt, alpha=alpha, beta=beta, adjust=adjust))
        if clip: self.callback_fns.append(partial(GradientClipping, clip=clip))
        if split_func: self.split(split_func)
        self.metrics = [accuracy]
        print(mode)
        if labelled_data != None:
            self.weights = calculate_weights(labelled_data, mode)
            self.loss_fn = partial(torch.nn.functional.cross_entropy, weight=self.weights)

    def save_encoder(self, name:str):
        '''Save the encoder to `name` inside the model directory.'''
        torch.save(self.model[0].state_dict(), self.path/self.model_dir/f'{name}.pth')

    def load_encoder(self, name:str):
        '''Load the encoder `name` from the model directory.'''
        self.model[0].load_state_dict(torch.load(self.path/self.model_dir/f'{name}.pth'))
        self.freeze()

    def load_encoder_path(self, path:str):
        self.model[0].load_state_dict(torch.load(path))

    def load_pretrained(self, wgts_fname:str, itos_fname:str):
        '''Load a pretrained model and adapts it to the data vocabulary.'''
        old_itos = pickle.load(open(self.path/self.model_dir/f'{itos_fname}.pkl', 'rb'))
        old_stoi = {v:k for k,v in enumerate(old_itos)}
        wgts = torch.load(self.path/self.model_dir/f'{wgts_fname}.pth', map_location=lambda storage, loc: storage)
        wgts = convert_weights(wgts, old_stoi, self.data.train_ds.vocab.itos)
        self.model.load_state_dict(wgts)

    @classmethod
    def language_model(cls, data:DataBunch, bptt:int=70, emb_sz:int=400, nh:int=1150, nl:int=3, pad_token:int=1,
                       drop_mult:float=1., tie_weights:bool=True, bias:bool=True, qrnn:bool=False,
                       pretrained_fnames:OptStrTuple=None, **kwargs) -> 'RNNLearner':
        '''Create a `Learner` with a language model.'''
        dps = np.array([0.25, 0.1, 0.2, 0.02, 0.15]) * drop_mult
        vocab_size = len(data.train_ds.vocab.itos)
        model = get_language_model(vocab_size, emb_sz, nh, nl, pad_token, input_p=dps[0], output_p=dps[1],
                    weight_p=dps[2], embed_p=dps[3], hidden_p=dps[4], tie_weights=tie_weights, bias=bias, qrnn=qrnn)
        learn = cls(data, model, bptt, split_func=lm_split, **kwargs)
        if pretrained_fnames is not None:
            learn.load_pretrained(*pretrained_fnames)
            learn.freeze()
        return learn

    @classmethod
    def classifier(cls, data:DataBunch, bptt:int=70, max_len:int=70*20, emb_sz:int=400, nh:int=1150, nl:int=3,
                   lin_ftrs:Collection[int]=None, ps:Collection[float]=None, pad_token:int=1,
                   drop_mult:float=1., qrnn:bool=False, labelled_data:Collection[int]=None, **kwargs) -> 'RNNLearner':
        '''Create a RNN classifier.'''

        #implimenting weights for parameters
        dps = np.array([0.4,0.5,0.05,0.3,0.4]) * drop_mult
        if lin_ftrs is None: lin_ftrs = [50]
        if ps is None:  ps = [0.1]
        vocab_size = len(data.train_ds.vocab.itos)
        n_class = len(data.train_ds.classes)
        layers = [emb_sz*3] + lin_ftrs + [n_class]
        ps = [dps[4]] + ps
        model = get_rnn_classifier(bptt, max_len, n_class, vocab_size, emb_sz, nh, nl, pad_token,
                    layers, ps, input_p=dps[0], weight_p=dps[1], embed_p=dps[2], hidden_p=dps[3], qrnn=qrnn)
        learn = cls(data, model, bptt, split_func=rnn_classifier_split, labelled_data=labelled_data, **kwargs)
        return learn
