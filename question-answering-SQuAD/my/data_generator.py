import argparse
import numpy as np
import pandas as pd
import data_loader
from nltk.tokenize.moses import MosesTokenizer
from keras.preprocessing.text import Tokenizer, text_to_word_sequence
from keras.preprocessing.sequence import pad_sequences

class DataGenerator():
    def __init__(self,
                 inputs=None,
                 tokenized_corpus=None,
                 embedding_vectors=None,
                 embedding_dim=None,
                 max_word_num=None,
                 max_sequence_len=None):
        
        super(DataGenerator, self).__init__()
        
        self.data = None
        self.context_vector = None
        self.question_vector = None
        self.answer_token_index = None # [start_location, end_location]
        self.vocabulary = None
        self.tokenizer = None
        self.embedding_matrix = None
        self.embedding_dim = embedding_dim
        
        self.context_vector, self.question_vector = self.get_vector(inputs, tokenized_corpus, max_word_num, max_sequence_len)
        self.answer_token_index = self.char_to_token_loc_mapping()
        self.embedding_matrix = self.get_embedding_matrix(embedding_vectors, embedding_dim)
    
    def read_word_pair(self, input):
        t = {}
        f = open(input, 'r')
        
        for line in f:
            key_val = line.rstrip().rsplit(' ')
            
            if len(key_val[1:]) == 1: # to read vocabulary (key=word, value=index)
                t[key_val[0]] = int(key_val[1])
            else: # to read embedding vectors (key=word, value=embedding vector)
                t[key_val[0]] = np.asarray(key_val[1:], dtype='float32')
        f.close()
        
        return t
    
    def create_vocab(self, inputs, maximum_word_num):
        '''
        create vocabulary based on tokenzied corpus
        '''
        # make tokenizer. But just used for word indexer
        tokenizer = Tokenizer(num_words = maximum_word_num+1, filters='', oov_token='UNK')
        
        # fit on input (tokenized) corpus
        f = open(inputs, 'r')
        corpus = [line for line in f]
        tokenizer.fit_on_texts(corpus)
        
        # create vocabulary
        tokenizer.word_index = {word:index for word, index in tokenizer.word_index.items() if index <= maximum_word_num}
        vocabulary = tokenizer.word_index
        
        print('number of unique tokens: {}'.format(len(vocabulary)))
        
        return tokenizer, vocabulary
    
    def char_to_token_loc_mapping(self):
        '''
        Mapping from character location in context to the corresponding token locations.
        Then, add answer start/end token index columns to the data.
            original text: self.data.context[c_i]
            tokenized text: c_tk
            token index: self.data.context_tk_index[c_i]
        '''
        nltk_tokenizer = MosesTokenizer()
        
        answer_start_token_idx_list, answer_end_token_idx_list = [], []
        for c_i, c_tk in enumerate(self.data.context_tk):
            answer_start = nltk_tokenizer.tokenize(self.data.context[c_i][self.data.answer_start[c_i]:], escape=False) # context text from the first answer token to end
            answer_end = nltk_tokenizer.tokenize(self.data.context[c_i][:self.data.answer_end[c_i]+1], escape=False) # context text from the first to end of answer token
            
            answer_start_token_idx = len(c_tk)- len(answer_start)
            answer_end_token_idx = answer_start_token_idx # initialize to start token location
    
            for i, tk in enumerate(c_tk[answer_start_token_idx:]):
                if tk == answer_end[-1]: # add to the index as many steps as it's moved to find the end of answer token
                    answer_end_token_idx += i
                    break
        
            '''
            Codes for verification:
                print(self.data.answer_text[c_i]) - Saint Bernadette Soubirous
                print(c_tk[answer_start_token_idx:answer_end_token_idx+1]) - ['Saint', 'Bernadette', 'Soubirous']
                for m in range(answer_start_token_idx, answer_end_token_idx+1): - 849 39352 39353
                    print(self.tokenizer.word_index[c_tk[m].lower()], end =' ')
                print(answer_start_token_idx, answer_end_token_idx) - 102 104
            '''
            
            pad_counts = np.count_nonzero(self.context_vector[c_i] == 0)
            
            answer_start_token_idx_list.append(answer_start_token_idx + pad_counts)
            answer_end_token_idx_list.append(answer_end_token_idx + pad_counts)
            # print(self.context_vector[c_i][answer_start_token_idx_list[c_i]:answer_end_token_idx_list[c_i]+1])
            
        return list(zip(answer_start_token_idx_list, answer_end_token_idx_list))

    def get_vector(self, inputs, tokenized_corpus, max_word_num, max_sequence_len):
        loader = data_loader.DataLoader(inputs)
        self.data = pd.DataFrame({'title': loader.title, 'context': loader.context, 'question':loader.question, 'answer_start':loader.answer_start, 'answer_end':loader.answer_end, 'answer_text':loader.answer_text})
            
        self.tokenizer, self.vocabulary = self.create_vocab(tokenized_corpus, max_word_num)
                            
        # tokenization & add tokens, token indexes to columns
        nltk_tokenizer = MosesTokenizer()
        vectors = []
        for i, text_column in enumerate(['context' , 'question']):
            self.data[text_column + '_tk'] = self.data[text_column].apply(lambda i: nltk_tokenizer.tokenize(i.replace('\n', '').strip(), escape=False))
        
            # token to index
            self.data[text_column+'_tk_index'] = self.tokenizer.texts_to_sequences(self.data[text_column + '_tk'].apply(lambda i: ' '.join(i)))
            
            # padding: It returns context, question vectors.
            vectors.append(pad_sequences(self.data[text_column+'_tk_index'], max_sequence_len[i]))

        return vectors

    def get_embedding_matrix(self, embedding_vectors, embedding_dim):
        trained_wv = self.read_word_pair(embedding_vectors) # read (pre)trained embedding word vectors
        print('number of trained word vector: {}'.format(len(trained_wv)))
    
        embedding_matrix = np.zeros((len(self.vocabulary)+1, embedding_dim)) # Glove: (-1, 100)
        for word, idx in self.vocabulary.items():
            embedding_wv = trained_wv.get(word)
            if embedding_wv is not None:
                embedding_matrix[idx] = embedding_wv
            # else:
            # print(word, idx, embedding_wv)
        print('embedding matrix shape: {}'.format(embedding_matrix.shape))

        return embedding_matrix

if __name__ == "__main__":
    inputs = 'data/train-v1.1.json'
    tokenized_corpus = 'corpus.tk.txt'
    embedding_vectors = '/Users/hoyeonlee/glove.6B/glove.6B.100d.txt'
    embedding_dim = 100
    max_word_num = 100000
    max_sequence_len = [300, 30]

    gen = DataGenerator(inputs, tokenized_corpus, embedding_vectors, embedding_dim, max_word_num, max_sequence_len)
