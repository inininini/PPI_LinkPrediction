import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
import scipy.sparse as sp
import matplotlib.pyplot as plt
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import auc, roc_curve





class AutoEnc(nn.Module):
    def __init__(self, in_dim):
        super().__init__()
        self.encoder = torch.nn.Sequential(
            nn.Linear(in_dim, in_dim//4),
            nn.ReLU(),
            nn.Linear(in_dim//4, in_dim//8),
            nn.ReLU(),
            nn.Linear(in_dim//8, in_dim//16),
        )
        self.decoder = torch.nn.Sequential(
            nn.Linear(in_dim//16, in_dim//8),
            nn.ReLU(),
            nn.Linear(in_dim//8, in_dim//4),
            nn.ReLU(),
            nn.Linear(in_dim//4, in_dim),
            nn.Sigmoid()
        )

    def forward(self, features):
        encoded = self.encoder(features)
        decoded = self.decoder(encoded)
        return decoded
    


class LinkPredDataset(Dataset):
    def __init__(self, mat):
        self.mat = mat
        
    def __len__(self):
        return self.mat.size(0)
    
    def __getitem__(self, index):
        return self.mat[index]



def main(data_file, epoch, batch_size):

    device = torch.device("cuda:0" if torch.cuda.is_available() else torch.device("cpu"))
    print('device : ', device)

    # data_df = pd.read_csv(data_file).head(500)
    data_df = pd.read_csv(data_file)
    print('data loading done')

    mat_df = pd.crosstab(data_df['gene_a'], data_df['gene_b'])
    idx = mat_df.columns.union(mat_df.index)
    mat_df = mat_df.reindex(index = idx, columns=idx, fill_value=0)
    mat = mat_df.values
    print('cross table done with the size of ', mat.shape)




    permut = np.random.permutation(mat.shape[0])
    train_num = int(mat.shape[0]*0.8)
    train_idx = permut[:train_num]
    test_idx = permut[train_num:]

    mat = torch.tensor(mat).float()
    mat_train = mat[train_idx]
    mat_test = mat[test_idx]




    train_ds = LinkPredDataset(mat_train)
    train_dl = DataLoader(train_ds, 
                        batch_size=batch_size,
                        shuffle=True,
                        num_workers=1,
                        drop_last=False)

    test_ds = LinkPredDataset(mat_test)
    test_dl = DataLoader(test_ds,batch_size=batch_size,
                        shuffle=False,
                        num_workers=1,
                        drop_last=False)
    




    model = AutoEnc(mat.size(1)).to(device)
    loss_func = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay = 1e8)



    outputs, losses, auc_score = [], [], []



    for e in range(epoch):
        model.train()

        print("------------- EPOCH {} -------------".format(e))
        for b, mat in enumerate(train_dl):
            input = mat.to(device)

            reconstructed = model(input).to(device)
            loss = loss_func(reconstructed, input)

            optimizer.zero_grad()
            loss.backward(retain_graph=True)
            optimizer.step()
            print("batch", b, "Loss", loss)

            losses.append(loss.detach())
            outputs.append((epoch, input, reconstructed))

            
            model.eval()
            with torch.no_grad():
                score = []
                for test_mat in test_dl:
                    test_input = test_mat.to(device)
                    test_reconstructed = model(test_input).to(device)
                    
                    true = test_input.reshape(-1).cpu().numpy()
                    pred = test_reconstructed.reshape(-1).cpu().numpy()
                    fpr, tpr, thresholds = roc_curve(true, pred, pos_label = 1)
                    score.append(auc(fpr, tpr))
                print("AUC", np.mean(score))
                auc_score.append(np.mean(score))


if __name__ == '__main__':
    main(data_file = 'context-PPI_final.csv',
                             epoch = 2, 
                             batch_size = 64)
    
    
    
