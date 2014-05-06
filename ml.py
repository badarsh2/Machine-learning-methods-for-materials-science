from sklearn import neighbors
from sklearn.decomposition import PCA, KernelPCA
import numpy as np
import pickle
from pylab import *
from ase.units import Bohr
from read_json import attribute_tolist, read_json
from split_dataset import *
from atomic_constants import pauling, radius, row, col, Zval, Eatom, Eion, Emadelung, charge, mus


def get_dpair():
    pkl_file = open('Spair.pkl', 'rb')
    dpair = pickle.load(pkl_file)
    pkl_file.close()
    return dpair


class kernel_ridge_regression:
    def __init__(self, mtrain, mcross, lamda, sigma, matrixtype=1):
        self.choice = matrixtype
        self.sigma = sigma
        self.lamda = lamda
        self.mtrain = mtrain
        self.mcross = mcross

        if matrixtype==2:
            self.dpair = get_dpair()
        

    def set_coulumb_matrix(self, atoms):
        # set coulomb matrix for a single solid
        na = atoms.natoms
        Z = atoms.Z 
        V = np.zeros((na, na))
    
        for i in range(na):
            for j in range(na):
                if i == j:
                    V[i, j] = 0.5 * Z[i]**2.4
                else:
                    d = (atoms.positions[i] - atoms.positions[j]) / Bohr
                    V[i, j] = Z[i] * Z[j] / np.sqrt(np.dot(d, d))
    
        E = np.linalg.eig(V)[0]
        E /= np.sum(np.abs(E))

        elements = set(atoms.names)
        ne = len(elements)
        
        return E
    
    def set_all_coulumb_matrix(self, choice=1, mset=None):
    
        if choice == 1:
            nset = len(mset) # number of training set
            M = {} 
            for i, atoms in enumerate(mset):
                M["%s"%(atoms.icsdno)] = self.set_coulumb_matrix(atoms)
            return M # matrix dictionary by icsdno
    
        elif choice == 2: # vladan
            pkl_file = open('Smatrix.pkl', 'rb')
            s_matrix = pickle.load(pkl_file)
            pkl_file.close()
            return s_matrix
        else:
            "Not implemented"
            XX
    
    
    def distance(self, M1, M2, icsd1=None, icsd2=None):
        if M1.ndim == 1 and M2.ndim == 1:
            n = max(len(M1), len(M2))
            M1 = np.append(M1, np.zeros(n-len(M1)))
            M2 = np.append(M2, np.zeros(n-len(M2)))
            return np.sqrt(np.dot(M1-M2, M1-M2))
        elif M1.ndim == 2 and M2.ndim == 2:
            if icsd1 is None:
                return np.trace(np.dot(M1-M2,M1-M2))
            else:
                return self.dpair[(icsd1, icsd2)]
        else:
            XX

    
    def regression(self, mset, M, sigma, lamda, kernel="laplacian"):
        # lamda for regularization, sigma for gaussian damping
        nset = len(mset) # number of training set
        Eref = attribute_tolist(mset, attr="Eref")
    
        K = np.zeros((nset, nset))
        for i in range(nset):
            M1 = M["%s"%(mset[i].icsdno)]
            for j in range(nset):
                M2 = M["%s"%(mset[j].icsdno)]
                K[i, j] = self.get_kernel(self.distance(M1, M2, mset[i].icsdno, mset[j].icsdno), sigma, kernel=kernel)
            K[i, i] += lamda
        print "Finished kernel"
    
        alpha = np.dot(np.linalg.inv(K), Eref) # not sure about the order
        return alpha
    
    
    def get_kernel(self, d, sigma, kernel="gaussian"):
        if kernel == "gaussian":
            return np.exp(- d**2 / (2.*sigma**2))
        elif kernel == "laplacian":
            return np.exp(-np.abs(d)/sigma)
        else:
            print "kernel not defined"
            XX
    
    def estimation(self, mtrain, M, alpha, sigma, mcross=None, Mref=None, kernel="laplacian"):
    
        ni = len(mcross)
        nj = len(mtrain)
        Eref = attribute_tolist(mcross, attr="Eref")

        MAE = 0
        for i in range(ni):
            Eest = 0 # estimation for set number i
            M1 = Mref["%s"%(mcross[i].icsdno)]
            for j in range(nj):
                M2 = M["%s"%(mtrain[j].icsdno)]
                Eest += alpha[j] * self.get_kernel(self.distance(M1, M2, mcross[i].icsdno, mtrain[j].icsdno), sigma, kernel=kernel)
            MAE += np.abs(Eest - Eref[i])
    #        print mset[i].formula, mset[i].natoms, mset[i].ncell, Eest, Eref[i], Eest - Eref[i]
        return MAE / ni

    def run(self, sigma=None, lamda=None):
        if sigma is None and lamda is None:
            sigma = self.sigma
            lamda = self.lamda
        M = self.set_all_coulumb_matrix(choice=self.choice, mset=self.mtrain)
        Mref = self.set_all_coulumb_matrix(choice=self.choice, mset=self.mcross)
        alpha = self.regression(self.mtrain, M, sigma, lamda)
        MAEtrain =  self.estimation(self.mtrain, M, alpha, sigma, self.mtrain, M)
        MAEcross = self.estimation(self.mtrain, M, alpha, sigma, self.mcross, Mref)
        
        return MAEtrain, MAEcross


    def choose_lamda_sigma(self, sigmalist, lamdalist):
        for sigma in sigmalist: 
            for lamda in lamdalist:
                print sigma, lamda, self.run(sigma, lamda)
    

def get_X(mtrain, mcross, scaling=1):

    Etrain = np.array(attribute_tolist(mtrain, attr="Eref"))
    Ecross = np.array(attribute_tolist(mcross, attr="Eref"))

    ndim = 10
    Xtrain = np.zeros((len(Etrain), ndim)); Xcross = np.zeros((len(Ecross), ndim))
    for mset in (mtrain, mcross):
        for i, atoms in enumerate(mset):
            nn = atoms.natoms
            elecneg = []
            rad = []
            mass = atoms.masses
            rowlist = []
            collist = []
            Eionization = []
            for ii, name in enumerate(atoms.names):
                elecneg.append(pauling[name])
                rad.append(radius[name])
                rowlist.append(row[name])
                collist.append(col[name])
                Eionization.append(Eion[name])

            val = [atoms.exptvol, np.mean(rad), np.mean(elecneg), np.mean(mass), np.max(rad)-np.min(rad), np.max(elecneg)-np.min(elecneg),
                   np.max(mass)-np.min(mass), np.max(rowlist)-np.min(rowlist), np.max(collist)-np.min(collist), np.mean(Eionization)]
#                   atoms.avg_cord]#, atoms.latt_a, atoms.latt_b, atoms.latt_c, atoms.alpha, atoms.beta, atoms.gamma]

            if mset == mtrain:
                Xtrain[i] = val
            elif mset == mcross:
                Xcross[i] = val
                
    # feature normalization
    for i in range(ndim):
        if scaling == 1: 
            xmean = np.mean(Xtrain[:,i])
            xstd = np.std(Xtrain[:,i])
            Xtrain[:,i] = (Xtrain[:, i] - xmean) / xstd
            Xcross[:,i] = (Xcross[:, i] - xmean) / xstd
        elif scaling == 2:
            Xtrain[:, i] = Xtrain[:, i] - np.min(Xtrain[:, i]) / (np.max(Xtrain[:, i]) - np.min(Xtrain[:, i]))
            Xcross[:, i] = Xcross[:, i] - np.min(Xcross[:, i]) / (np.max(Xcross[:, i]) - np.min(Xcross[:, i]))
        elif scaling == 3:
            Xtrain[:, i] /= np.sqrt(np.inner(Xtrain[:, i], Xtrain[:, i]))
            Xcross[:, i] /= np.sqrt(np.inner(Xcross[:, i], Xcross[:, i]))

    return Xtrain, Xcross, Etrain, Ecross


def knn_regression(mtrain, mcross, n_ngh):
    for kernel in ([None, 'rbf', 'poly','cosine']):
        for scaling in ([1, 2, 3]):
            Xtrain, Xcross, Etrain, Ecross = get_X(mtrain, mcross, scaling)
            Xtrain, Xcross = pca_decomposition(Xtrain, Xcross, n_components=7, kernel=kernel)
        
            n_neighbors = n_ngh
            knn = neighbors.KNeighborsRegressor(n_neighbors, weights="distance")
            model = knn.fit(Xtrain, Etrain)
        
            Epredict = model.predict(Xcross)
            print kernel, scaling, np.nansum(np.abs(Epredict - Ecross)) / len(Ecross) # MAE
    #    for i, atoms in enumerate(mcross):
    #        print atoms.formula, Epredict[i], Ecross[i], np.abs(Epredict[i] - Ecross[i])
    #        plot(Epredict[i], Ecross[i], '+r')
    #        text(Epredict[i], Ecross[i], atoms.formula)
    #    plot(Ecross, Ecross, '-k')
    #    show()
        
    return 


def krr_regression(mtrain, mcross, sigma=50, lamda=0.01):
    Xtrain, Xcross, Etrain, Ecross = get_X(mtrain, mcross)

    K_ij = np.zeros((len(Etrain), len(Etrain)))
    for i in range(len(Etrain)):
        for j in range(len(Etrain)):
            d = Xtrain[i] - Xtrain[j]
            dd = np.sqrt(np.inner(d, d))
            K_ij[i, j] = np.exp(-dd / sigma)
        K_ij[i, i] += lamda
    alpha = np.dot(np.linalg.inv(K_ij), Etrain) # not sure about the order

    def get_MAE(X, E):
        MAE = 0
        for i in range(len(E)):
            Eest = 0 # estimation for set number i
            for j in range(len(Etrain)):
                d = Xtrain[j] - X[i]
                dd = np.sqrt(np.inner(d, d))
                Eest += alpha[j] * np.exp(-dd / sigma) 
            MAE += np.abs(Eest - E[i])
        return MAE / len(E)

    return get_MAE(Xtrain, Etrain), get_MAE(Xcross, Ecross)


def pca_decomposition(Xtrain, Xcross, n_components=7, kernel=None):
    if kernel is None:
        pca = PCA(n_components=n_components)
    else:
        pca = KernelPCA(kernel=kernel, n_components=n_components)

    Xtrain = pca.fit_transform(Xtrain)    
    Xcross = pca.transform(Xcross)
    if kernel is None:  print(pca.explained_variance_ratio_), (pca.explained_variance_ratio_).sum()
    return Xtrain, Xcross
    

if __name__ == "__main__":
    mset = read_json("data.json")
    mtest, mset = get_testset(mset)
    mtrain, mcross, mset = get_train_validation_set(mset)
    sigma = 50
    lamda = 0.01

    kRR = kernel_ridge_regression(mtrain, mcross, lamda, sigma, matrixtype=1)
    print kRR.run()
    kRR.choose_lamda_sigma([10, 50], [0.01, 0.001])

    print knn_regression(mtrain, mcross, 5)
