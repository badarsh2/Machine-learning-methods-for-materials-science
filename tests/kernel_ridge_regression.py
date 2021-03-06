import os
from read_json import read_json
from split_dataset import *
from ml import *
np.random.seed(0)

mset = read_json("data.json")
assert len(mset) == 1155

mtest, mset = get_testset(mset)
mtrain, mcross, mset = get_train_validation_set(mset)

sigma = 50 ; lamda = 0.01    
kRR = kernel_ridge_regression(mtrain, mcross, lamda, sigma, matrixtype=1)
MAEtrain, MAEcross =  kRR.run()

assert np.abs(MAEtrain - 0.61441313521708385) < 1e-6
assert np.abs(MAEcross - 0.68636581583959533) < 1e-6

#kRR.choose_lamda_sigma([10, 50], [0.01, 0.001])
