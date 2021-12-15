import lime
import lime.lime_tabular
import numpy as np
import shap

from utils import reorder_attributes


def set_up_explainer(xai_sol, parameters, context):
    """
    Initialize the explainer object for solutions that need it.

    Parameters
    ----------
    xai_sol : str
        Name of the XAI solution that is initialized.
    parameters : dict
        Parameters of the XAI solution for the initialization.
    context : dict
        Information of the context that may change the process.

    Returns
    -------
    object
        Explainer object that can be used to generate explanation.
    """    
    if xai_sol == "LIME":

        X=context["X"]
        y=context["y"]
        feature_names=context["feature_names"]
        verbose=context["verbose"]
        mode=context["task"]

        explainer = lime.lime_tabular.LimeTabularExplainer(training_data=X, feature_names=feature_names, training_labels=y, verbose=verbose, mode=mode, discretize_continuous=False)    
    
    elif xai_sol == "SHAP":
        #TODO use shap.Explainer for genericity
        X=context["X"]
        m = context['model']
        summarize = parameters['summarize']

        if summarize == "Sampling":
            explainer = shap.explainers.Sampling(m.predict, X)
        else :
            explainer = shap.KernelExplainer(m.predict, X)


    return explainer

def get_local_exp(xai_sol, x, parameters, context):
    """
    Calculates a local explanation and formats it for future evaluation.

    Parameters
    ----------
    xai_sol : str
        Name of the XAI solution that is used to get explanation.
    x : list or numpy array
        Data point for which we want the explanation of the black box 
    parameters : dict
        Parameters of the XAI solution for the local explanation.
    context : dict
        Information of the context that may change the process.

    Returns
    -------
    list
        Vector of feature influence constituting the explanation.
    """    
    if xai_sol == "LIME":

        explainer = context['explainer']
        m = context['model']
        feature_names = context['feature_names']
        num_samples = parameters['num_samples']

        e = reorder_attributes(dict(explainer.explain_instance(x, m.predict, num_samples=num_samples).as_list()), feature_names)

    if xai_sol == "SHAP":
        explainer = context['explainer']
        nsamples = parameters['nsamples']
        l1_reg = parameters['l1_reg']

        e = explainer.shap_values(x,nsamples=nsamples,l1_reg=l1_reg)
        # print("------SHAP-----")
        # print(x)
        # print(e)

    return e[:parameters['nfeatures']]