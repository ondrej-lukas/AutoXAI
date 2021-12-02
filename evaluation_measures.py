import numpy as np
from tqdm import tqdm
from skopt import gp_minimize
from functools import partial
from XAI_solutions import set_up_explainer, get_local_exp
from sklearn.preprocessing import MinMaxScaler, StandardScaler
import pickle
import os

import warnings
warnings.filterwarnings('ignore')

def lipschitz_ratio(x, y, function, reshape=None, minus=False):

    # Need this ugly hack because skopt sends lists
    if type(x) is list:
        x = np.array(x)
    if type(y) is list:
        y = np.array(y)
    if type(function(x)) is list:
        fx = np.array(function(x))
    else:
        fx = function(x)
    if type(function(y)) is list:
        fy = np.array(function(y))
    else:
        fy = function(y)

    if reshape is not None:
        # Necessary because gpopt requires to flatten things, need to restrore expected sshape here
        x = x.reshape(reshape)
        y = y.reshape(reshape)
    #print(x.shape, x.ndim)
    multip = -1 if minus else 1

    return multip * np.linalg.norm(fx - fy) / np.linalg.norm(x - y)

def compute_lipschitz_robustness(xai_sol, parameters, context):
    es=True
    IS=True
    session_id = '0'
    X=context["X"]
    verbose=context["verbose"]

    eps = 0.1
    njobs = -1
    if xai_sol in ['LIME','SHAP']:
        n_calls = 10
    else:
        n_calls = 100

    def exp(x):
        return get_local_exp(xai_sol, x, parameters, context)
    
    list_lip = []

    path = 'results/x_opts_'+xai_sol+session_id+'.p'
    if IS and os.path.exists(path):
        # print('Robustness uses previously computed points')
        x_opts = pickle.load(open(path, "rb"))
        for i in tqdm(range(len(x_opts))):
            lip = lipschitz_ratio(X[i],x_opts[i],exp)
            list_lip.append(lip)

    else:
        x_opts = []

        # for i in tqdm(range(2)):
        for i in tqdm(range(len(X))):
            x = X[i]
            orig_shape = x.shape
            lwr = (x - eps).flatten()
            upr = (x + eps).flatten()
            bounds = list(zip(*[lwr, upr]))
            f = partial(lipschitz_ratio, x, function=exp,
                        reshape=orig_shape, minus=True)
            res = gp_minimize(f, bounds, n_calls=n_calls,
                                verbose=verbose, n_jobs=njobs)
            lip, x_opt = -res['fun'], np.array(res['x'])
            list_lip.append(lip)
            x_opts.append(x_opt)

            # print(" ES rob")
            # print(abs(np.mean(list_lip[:-1])-np.mean(list_lip)))
            # print(np.mean(list_lip)/10)
            if es and abs(np.mean(list_lip[:-1])-np.mean(list_lip)) <= np.mean(list_lip)/10:
                break

    if IS and not os.path.exists(path):
        pickle.dump(x_opts, open(path, "wb"))

    score = np.mean(list_lip)
    return score

def compute_infidelity(xai_sol, parameters, context):
    es=True
    IS=True
    session_id='0'
    X = context["X"]
    model = context['model']
    eps = 0.1
    nb_pert = 10
    list_inf = []

    path = 'results/perturb_infs_'+xai_sol+session_id+'.p'
    if IS and os.path.exists(path):
        # print('Fidelity uses previously computed points')
        perturb_infs = pickle.load(open(path, "rb"))
        for i in tqdm(range(len(perturb_infs))):
            x = X[i]
            pertubation_diff = []
            for j in range(nb_pert):
                x0 = perturb_infs[i]['x0'][j]
                exp = get_local_exp(xai_sol, x, parameters, context)[:parameters['nfeatures']]
                exp_x = np.matmul(x[:parameters['nfeatures']],np.asarray(exp).T)
                exp_x0 = np.matmul(x0[:parameters['nfeatures']],np.asarray(exp).T)
                pred_x = perturb_infs[i]['pred_x'][j]
                pred_x0 = perturb_infs[i]['pred_x0'][j]
                pertubation_diff.append((exp_x-exp_x0-(pred_x-pred_x0))**2)
            list_inf.append(np.mean(pertubation_diff))
    else:
        # for i in tqdm(range(2)):
        perturb_infs = []
        for i in tqdm(range(len(X))):
            x = X[i]
            pertubation_diff = []
            pert = {'x0':[],'pred_x':[],'pred_x0':[]}
            for j in range(nb_pert):
                x0 = x + np.random.rand(len(x))*2*eps-eps
                exp = get_local_exp(xai_sol, x, parameters, context)[:parameters['nfeatures']]
                # exp0 = get_local_exp(xai_sol, x, parameters, context)
                exp_x = np.matmul(x[:parameters['nfeatures']],np.asarray(exp).T)
                exp_x0 = np.matmul(x0[:parameters['nfeatures']],np.asarray(exp).T)
                pred_x = model.predict(x.reshape(1, -1))[0]
                pred_x0 = model.predict(x0.reshape(1, -1))[0]
                pertubation_diff.append((exp_x-exp_x0-(pred_x-pred_x0))**2)

                pert['x0'].append(x0)
                pert['pred_x'].append(pred_x)
                pert['pred_x0'].append(pred_x0)

            perturb_infs.append(pert)

            list_inf.append(np.mean(pertubation_diff))
            # print(" ES fid")
            # print(abs(np.mean(list_inf[:-1])-np.mean(list_inf)))
            # print(np.mean(list_inf)/10)
            if es and abs(np.mean(list_inf[:-1])-np.mean(list_inf)) <= np.mean(list_inf)/10:
                break
    if IS and not os.path.exists(path):
        pickle.dump(perturb_infs, open(path, "wb"))

    score = np.mean(list_inf)
    return score

def evaluate(xai_sol, parameters, property, context):
    # Set up of XAI solutions before computing evaluation
    if xai_sol in ['LIME','SHAP']:
        context['explainer'] = set_up_explainer(xai_sol, parameters, context)
    
    # Computing evaluation for specified property
    if property == 'robustness':
        if context['question']=="Why":
            score = compute_lipschitz_robustness(xai_sol, parameters, context)
    if property == 'fidelity':
        if context['question']=="Why":
            score = compute_infidelity(xai_sol, parameters, context)
    if property == 'conciseness':
        if context['question']=="Why":
            score = parameters['nfeatures']
    return score

def linear_scalarization(score_hist, properties_list, context):
    scaling = context["scaling"]
    weights = context["weights"]

    score_hist["aggregated_score"] = np.zeros(len(score_hist["aggregated_score"])+1)

    for i,property in enumerate(properties_list):
        if len(score_hist[property])>1:
            if scaling == "MinMax":
                scaler = MinMaxScaler()
            if scaling == "Std":
                scaler = StandardScaler()
            score_hist["scaled_"+property] = scaler.fit_transform(np.asarray(score_hist[property]).reshape(-1, 1)).reshape(1, -1).tolist()[0]
            # print("debug")
            # print(score_hist[property])
            # print(np.asarray(score_hist["scaled_"+property]))
            # print(weights[i])
            # print(len(properties_list))
            # print("-----")
            # print(np.asarray(score_hist["scaled_"+property]) * weights[i]/len(properties_list))
            # print(score_hist["aggregated_score"])
            score_hist["aggregated_score"] += np.asarray(score_hist["scaled_"+property]).reshape(score_hist["aggregated_score"].shape) * weights[i]/len(properties_list)
        else :
            score_hist["scaled_"+property] = 0

    score_hist["aggregated_score"]=list(score_hist["aggregated_score"])

    return score_hist