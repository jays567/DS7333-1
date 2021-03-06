from sklearn.datasets import load_boston
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import Imputer
from sklearn.base import BaseEstimator
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Callable
from sklearn.impute import SimpleImputer
from pprint import pprint
plt.style.use('bmh')

# whip up the boston dataset
X, y = load_boston(return_X_y=True)

# default parameters to use
parameter_dict = {'n_jobs':-1}
# dictionary for results
results_dict = {}

def get_scores(features: np.ndarray,
               targets: np.ndarray,
               model_class: BaseEstimator=LinearRegression,
               pars: dict=parameter_dict) -> dict:
    model = model_class(**pars)
    model.fit(features, targets)
    preds = model.predict(features)
    goodness = r2_score(y, preds)
    loss = mean_squared_error(y, preds)
    return {'goodness_of_fit':goodness, 'mse':loss}



def random_miss(data: np.ndarray, prop: int) -> np.ndarray:
    if type(prop) is not int or prop <= 0 or prop >=100:
        raise ValueError('needs to be an int less than 100 and greater than zero!')
    nrows = data.shape[0]
    idy = np.random.choice(data.shape[-1], 1)
    idx = np.random.choice(nrows, int(nrows*prop/100), replace=False)
    out = data.copy()
    out[idx, idy] = np.nan
    return out

def _stats_dict(arr: list) -> dict:
    return {'avg': np.mean(arr), 'std': np.std(arr)}

def iterate_stats(features: np.ndarray,
                  targets: np.ndarray,
                  impute_method: str=None,
                  prop: int=0,
                  iters: int=10,
                  model_class: BaseEstimator=LinearRegression,
                  pars: dict=parameter_dict) -> dict:
    r2 = []
    mse = []
    for _ in range(iters):
        if prop ==  0:
            data = features
        else:
            tmp = random_miss(features, prop)
            data = SimpleImputer(strategy=impute_method).fit_transform(tmp)
            del tmp
        res = get_scores(data, targets, model_class, pars)
        r2 += [res['goodness_of_fit']]
        mse += [res['mse']]
    return {'goodness_of_fit': _stats_dict(r2), 'loss': _stats_dict(mse)}

results_dict['baseline'] = iterate_stats(X,y)

impute_types = ['mean','median']
miss_props = [1, 5, 10, 20, 33, 50]
n_rounds = X.shape[-1]*100

for imp in impute_types:
    results_dict[imp] = {p: iterate_stats(X, y, prop=p, iters=n_rounds, impute_method=imp) for p in miss_props}


def results_to_series(res: dict, f_type: str) -> dict:
    upper = []
    lower = []
    avg = []
    x = list(res.keys())
    avg = [res[k][f_type]['avg'] for k in x]
    std = [res[k][f_type]['std'] for k in x]
    # for plotting
    upper = [avg[i] + std[i] for i in range(len(avg))]
    lower = [avg[i] - std[i] for i in range(len(avg))]
    return {'x':x, 'y':avg, 'upper': upper, 'lower':lower}



def make_plotter(f_type: str) -> Callable:
    def plot_generic_stats(results: dict=results_dict)-> None:
        ax = plt.subplot()
        base = results_dict['baseline'][f_type]
        ax.axhline(base['avg'], color='r', xmin=0, xmax=50, label='Baseline')
        keys = [k for k in results.keys() if k != 'baseline']
        for k in keys:
            tmp = results_to_series(results[k], f_type)
            ax.plot(tmp['x'], tmp['y'], label=k.title())
            ax.fill_between(tmp['x'], tmp['lower'], tmp['upper'], alpha=0.1, label=f"{k} error".title())
        ax.legend()
        ax.set_title(f"{f_type} vs Percentage of Missing Data, by Imputation Method".title().replace("_"," "))
        ax.set_xlabel('Percentage of Missing Data')
        ax.set_ylabel(f_type.title().replace("_"," "))
        plt.show()
    return plot_generic_stats

plot_goodness = make_plotter('goodness_of_fit')
plot_loss = make_plotter('loss')

plot_loss()

plot_goodness()


## mnar!

def _mnar(arr: np.ndarray, col: int) -> np.ndarray:
    quant = np.quantile(arr[:, col], 0.75)
    idx = np.where(arr[:,col] >=  quant)
    out = arr.copy()
    out[idx, col] = np.nan
    na_percs = np.isnan(out).astype(int).sum(0) / out.shape[0]
    print(f"na_percentages: column {col} missing")
    pprint(na_percs.tolist())
    return out


mnar_dict = {}
for imp in impute_types:
    r2 = []
    mse = []
    for i in range(X.shape[-1]):
        data = _mnar(X, i)
        data_imputed = SimpleImputer(strategy=imp).fit_transform(data)
        scores = get_scores(data_imputed, y)
        r2 += [scores['goodness_of_fit']]
        mse += [scores['mse']]
    mnar_dict[imp] = {'goodness_of_fit': _stats_dict(r2), 'loss': _stats_dict(mse)}
mnar_dict['baseline'] = results_dict['baseline']

r2 = []
mse = []
for i in range(X.shape[-1]):
    data = _mnar(X,i)
    data_imputed = SimpleImputer(strategy='constant', fill_value=-100)
    scores = get_scores(data_imputed, y)
    r2 += [scores['goodness_of_fit']]
    mse += [scores['mse']]
mnar_dict['constant'] = {'goodness_of_fit': _stats_dict(r2), 'loss': _stats_dict(mse)}



ax = plt.subplot()
keys = list(mnar_dict.keys())
avgs = [mnar_dict[imp]['loss']['avg'] for imp in mnar_dict.keys()]
stds = [mnar_dict[imp]['loss']['std'] for imp in mnar_dict.keys()]
for k in range(len(keys)):
    ax.barh(keys[k], avgs[k], label = keys[k], xerr = stds[k])
ax.set_title('Loss of missing not at random imputation'.title())
ax.set_xlabel('Loss')
ax.set_ylabel('Imputation Method')
plt.show()


ax = plt.subplot()
keys = list(mnar_dict.keys())
avgs = [mnar_dict[imp]['goodness_of_fit']['avg'] for imp in mnar_dict.keys()]
stds = [mnar_dict[imp]['goodness_of_fit']['std'] for imp in mnar_dict.keys()]
for k in range(len(keys)):
    ax.barh(keys[k], avgs[k], label = keys[k], xerr = stds[k])
ax.set_title('Goodness of Fit of missing not at random imputation'.title())
ax.set_xlabel('Goodness of Fit')
ax.set_ylabel('Imputation Method')
plt.show()
