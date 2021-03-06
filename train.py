# -*- coding:utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import optparse
import numpy as np
import torch
from torch.jit import script, trace
import torch.nn as nn
from torch import optim
from torch.autograd import Variable
import torch.nn.functional as F
from torchtext.vocab import GloVe, Vectors
from torchtext import data, datasets, vocab
import csv
import random
import re
import os
import unicodedata
import codecs
from io import open
import itertools
import math
import time
from utils.util import *
from model import *
from eval import *
from data.duconv.dataloader import DuconvDataset, DuconvDataloader


optparser = optparse.OptionParser()
optparser.add_option(
    "-C", "--corpus_name", default="duconv",
    choices=['cornell-movie-dialogs-corpus', 'duconv'],
    help="Corpus name (cornell-movie-dialogs-corpus or duconv)"
)
optparser.add_option(
    "-F", "--data_file", default="formatted_dialog.txt",
    help="Data file name"
)
optparser.add_option(
    "-T", "--train_file", default="train.txt",
    help="Train file name"
)
optparser.add_option(
    "-E", "--test_file", default="dev.dat",
    help="Test file name"
)
optparser.add_option(
    "-G", "--glove_path", default='model/glove/sgns.wiki.bigram',
    help="Path of Glove word vector file"
)
optparser.add_option(
    "-A", "--attn_model", choices=['dot', 'general', 'concat'], default="general",
    help="Attention model"
)
optparser.add_option(
    "-H", "--hidden_size", default=300,
    help="Dimensionality of the glove word vector"
)
optparser.add_option(
    "--encoder_n_layers", default=2,
    help="Layer number of encoder"
)
optparser.add_option(
    "--decoder_n_layers", default=2,
    help="Layer number of decoder"
)
optparser.add_option(
    "-D", "--dropout", default=0.1,
    help="Dropout"
)
optparser.add_option(
    "-B", "--batch_size", default=32,
    help="Batch size"
)
optparser.add_option(
    "--clip", default=50.0,
    help="Clip gradients: gradients are modified in place"
)
optparser.add_option(
    "--teacher_forcing_ratio", default=1.0,
    help="Teacher forcing ratio"
)
optparser.add_option(
    "--decoder_learning_ratio", default=5.0,
    help="Decoder learning ratio"
)
optparser.add_option(
    "-L", "--learning_rate", default=0.0001,
    help="Learning rate"
)
optparser.add_option(
    "-N", "--n_iteration", default=4000,
    help="Epoch number"
)
optparser.add_option(
    "-P", "--print_every", default=10,
    help="Print frequency"
)
optparser.add_option(
    "-S", "--save_every", default=1000,
    help="Save frequency"
)
# optparser.add_option(
#     '--task_id', default=4,
#     help='bAbI task id'
# )
# optparser.add_option(
#     '--question_id', default=0,
#     help='question types'
# )
# optparser.add_option(
#     '--workers', default=2,
#     help='number of data loading workers'
# )
# optparser.add_option(
#     '--batchSize', default=10,
#     help='input batch size'
# )
# optparser.add_option(
#     '--state_dim', default=2913,
#     help='GGNN hidden state size'
# )
optparser.add_option(
    '--n_steps', default=5,
    help='propogation steps number of GGNN'
)
# optparser.add_option(
#     '--niter', default=10,
#     help='number of epochs to train for'
# )
# optparser.add_option(
#     '--lr', default=0.01,
#     help='learning rate'
# )
optparser.add_option(
    '--cuda', action='store_true',
    help='enables cuda'
)
optparser.add_option(
    '--verbal', action='store_true',
    help='print training info or not'
)
optparser.add_option(
    '--manualSeed',
    help='manual seed'
)


opts = optparser.parse_args()[0]

# Configure data file
corpus_name = opts.corpus_name
data_file = opts.data_file
train_file = opts.train_file
test_file = opts.test_file
glove_path = opts.glove_path
# Configure models
# model_name = 'cb_model'
attn_model = opts.attn_model
hidden_size = opts.hidden_size
encoder_n_layers = opts.encoder_n_layers
decoder_n_layers = opts.decoder_n_layers
dropout = opts.dropout
batch_size = opts.batch_size
# Configure training/optimization
clip = opts.clip
teacher_forcing_ratio = opts.teacher_forcing_ratio
decoder_learning_ratio = opts.decoder_learning_ratio
learning_rate = opts.learning_rate
n_iteration = opts.n_iteration
print_every = opts.print_every
save_every = opts.save_every
# Configure GNN
# state_dim = opts.state_dim
n_steps = opts.n_steps

corpus = os.path.join("data", corpus_name)
# Define path to new file
datafile = os.path.join(corpus, data_file)
trainfile = os.path.join(corpus, train_file)

USE_CUDA = torch.cuda.is_available()
device = torch.device("cuda" if USE_CUDA else "cpu")

MAX_LENGTH = 10
annotation_dim = 1

# Load/Assemble voc and pairs
cache = '.vector_cache'
if not os.path.exists(cache):
    os.mkdir(cache)

# TEXT.build_vocab(pos, vectors=GloVe(name='6B', dim=300))
save_dir = os.path.join("model", corpus_name)
voc, pairs = loadPrepareData(corpus_name, trainfile, datafile, MAX_LENGTH)
# Print some pairs to validate
# print("pairs:\n")
# for pair in pairs[:10]:
#     print(pair)

# Initialize dataset
dataset = DuconvDataset(trainfile, os.path.join(corpus, 'test.txt'), corpus_name, datafile, MAX_LENGTH)
dataloader = DuconvDataloader(dataset, batch_size, shuffle=True, num_workers=2)
print(dataloader.dataset)
# Trim voc and pairs
# pairs = trimRareWords(voc, pairs)

# Example for validation
# small_batch_size = 5
# batches = batch2TrainData(voc, [random.choice(pairs) for _ in range(small_batch_size)])
# input_variable, lengths, target_variable, mask, max_target_len = batches
#
# print("input_variable:", input_variable)
# print("lengths:", lengths)
# print("target_variable:", target_variable)
# print("mask:", mask)
# print("max_target_len:", max_target_len)

# Set checkpoint to load from; set to None if starting from scratch
loadFilename = None
# checkpoint_iter = 4000
# loadFilename = os.path.join(save_dir, model_name, corpus_name,
#                             '{}-{}_{}'.format(encoder_n_layers, decoder_n_layers, hidden_size),
#                             '{}_checkpoint.tar'.format(checkpoint_iter))


# Load model if a loadFilename is provided
if loadFilename:
    # If loading on same machine the model was trained on
    checkpoint = torch.load(loadFilename)
    # If loading a model trained on GPU to CPU
    # checkpoint = torch.load(loadFilename, map_location=torch.device('cpu'))
    encoder_sd = checkpoint['en']
    decoder_sd = checkpoint['de']
    encoder_optimizer_sd = checkpoint['en_opt']
    decoder_optimizer_sd = checkpoint['de_opt']
    embedding_sd = checkpoint['embedding']
    voc.__dict__ = checkpoint['voc_dict']


print('Building encoder and decoder ...')
# Initialize GNN
n_edge_types = dataset.n_edge_types
n_node = dataset.n_node
state_dim = dataset.state_dim
net = GGNN(state_dim, annotation_dim, n_edge_types, n_node, n_steps)
net.double()
print(net)

# Initialize word embeddings
embedding = nn.Embedding(voc.num_words, hidden_size)
weight_matrix = Vectors(glove_path)
voc.getEmb(weight_matrix)
print(torch.FloatTensor(np.array(voc.index2emb)).size())
embedding.weight.data.copy_(torch.FloatTensor(np.array(voc.index2emb)))
embedding.weight.requires_grad = False
if loadFilename:
    embedding.load_state_dict(embedding_sd)
# Initialize encoder & decoder models
encoder = EncoderRNN(hidden_size, embedding, encoder_n_layers, dropout)
decoder = LuongAttnDecoderRNN(attn_model, embedding, hidden_size, voc.num_words, decoder_n_layers, dropout)
if loadFilename:
    encoder.load_state_dict(encoder_sd)
    decoder.load_state_dict(decoder_sd)
seq2seq = Seq2Seq(encoder, decoder, net, opts)
# Use appropriate device
seq2seq.to(device)
print('Models built and ready to go!')


def train(input_variable, lengths, target_variable, mask, max_target_len, seq2seq,
          seq2seq_optimizer, adj_matrix, batch_size, clip, max_length=MAX_LENGTH):

    # Zero gradients
    seq2seq_optimizer.zero_grad()

    # Set device options
    input_variable = input_variable.to(device)
    lengths = lengths.to(device)
    target_variable = target_variable.to(device)
    mask = mask.to(device)

    # init_input = torch.zeros(n_node, state_dim - annotation_dim).double()
    init_input = torch.zeros(n_node, state_dim).double()
    init_input = init_input.to(device)
    adj_matrix = torch.FloatTensor(adj_matrix)
    print(adj_matrix.size())
    adj_matrix = adj_matrix.to(device)
    # annotation = annotation.to(device)
    # target = target.to(device)

    init_input = Variable(init_input)
    adj_matrix = Variable(adj_matrix)
    # annotation = Variable(annotation)
    # target = Variable(target)

    loss, print_losses, n_totals = seq2seq(input_variable, lengths, batch_size, teacher_forcing_ratio, max_target_len, target_variable, mask, init_input, adj_matrix)

    # Perform backpropatation
    loss.backward()

    # Clip gradients: gradients are modified in place
    _ = nn.utils.clip_grad_norm_(seq2seq.parameters(), clip)

    # Adjust model weights
    seq2seq_optimizer.step()

    return sum(print_losses) / n_totals


def trainIters(voc, pairs, seq2seq, seq2seq_optimizer, save_dir, n_iteration, batch_size, print_every, save_every, clip, loadFilename, time_str):

    # Load batches for each iteration
    training_batches = [batch2TrainData(voc, [random.choice(pairs) for _ in range(batch_size)])
                        for _ in range(n_iteration)]

    # Initializations
    print('Initializing ...')
    start_iteration = 1
    print_loss = 0
    if loadFilename:
        start_iteration = checkpoint['iteration'] + 1
    net.train()

    # Training loop
    print("Training...")
    adj_matrix = dataloader.dataset[0]
    print(adj_matrix)
    for iteration in range(start_iteration, n_iteration + 1):
        training_batch = training_batches[iteration - 1]
        # Extract fields from batch
        input_variable, lengths, target_variable, mask, max_target_len = training_batch

        # Run a training iteration with batch
        loss = train(input_variable, lengths, target_variable, mask, max_target_len, seq2seq, seq2seq_optimizer, adj_matrix, batch_size, clip)
        print_loss += loss

        # Print progress
        if iteration % print_every == 0:
            print_loss_avg = print_loss / print_every
            print("Iteration: {}; Percent complete: {:.1f}%; Average loss: {:.4f}".format(iteration, iteration / n_iteration * 100, print_loss_avg))
            print_loss = 0

        # Save checkpoint
        if iteration % save_every == 0:
            directory = os.path.join(save_dir, time_str)
            if not os.path.exists(directory):
                os.makedirs(directory)
            save_path = os.path.join(directory, '{}_{}.ml'.format(iteration, 'checkpoint'))
            torch.save(seq2seq, save_path)

    return save_path


# Ensure dropout layers are in train mode
seq2seq.train()

# Initialize optimizers
print('Building optimizers ...')
seq2seq_optimizer = optim.Adam(seq2seq.parameters(), lr=learning_rate)

# Run training iterations
print("Starting Training!")
time_str = time.strftime("%Y%m%d-%H%M%S", time.localtime())
writeParaLog(opts, time_str)
save_path = trainIters(voc, pairs, seq2seq, seq2seq_optimizer,
            save_dir, n_iteration, batch_size,
            print_every, save_every, clip, loadFilename, time_str)

# Set dropout layers to eval mode
seq2seq.eval()

# Initialize search module
searcher = GreedySearchDecoder(seq2seq)

test_path = os.path.join(corpus, test_file)
res_path = re.sub(r'\.ml', '.txt', save_path)
evaluateFile(searcher, voc, test_path, res_path, max_length=MAX_LENGTH)
print('Done! The model name is: ' + time_str)
