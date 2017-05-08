import numpy
import logging
from numpy.core import dot, array
from scipy import stats

from .. import Exceptions
from ..misc import Math
from .. import Utilities

class Context(object):
    def __init__(self): raise Exceptions.ReportableException("Tried to instantiate abstract Joint Analysis context")
    def get_genes(self): pass
    def get_metaxcan_zscores(self, gene): pass
    def get_model_matrix(self, gene, tissues): pass
    def get_cutoff(self, matrix): pass

class CalculationStatus(object):
    OK=0
    NO_DATA=-1
    NO_METAXCAN_RESULTS=-2
    NO_PRODUCT=-3
    INSUFFICIENT_NUMERICAL_RESOLUTION = -4
    SINGULAR_COVARIANCE = -5
#    COMPLEX_COVARIANCE = -6

def joint_analysis(context, gene):
    pvalue, n, n_indep, p_i_best, p_i_worst, eigen_max, eigen_min, status = None, None, None, None, None, None, None, CalculationStatus.NO_DATA
    g = gene.split(".")[0]

    zscores, tissue_labels = context.get_metaxcan_zscores(gene)
    if not zscores or len(zscores) == 0:
        status = CalculationStatus.NO_METAXCAN_RESULTS
        return g, pvalue, n, n_indep, p_i_best, p_i_worst, eigen_max, eigen_min, status
    n = len(zscores)

    labels, matrix = context.get_model_matrix(gene, tissue_labels)
    if not labels or len(labels) == 0:
        status = CalculationStatus.NO_PRODUCT
        return g, pvalue, n, n_indep, p_i_best, p_i_worst, eigen_max, eigen_min, status

    e, v = numpy.linalg.eig(matrix)
    eigen_max, eigen_min = numpy.max(e), numpy.min(e)

    #eigen_max_i, eigen_min_i = float(numpy.imag(eigen_max)), float(numpy.imag(eigen_min))
    #if eigen_max_i != 0 or eigen_min_i != 0:
    #    from IPython import embed; embed(); exit(0)
    #    status = CalculationStatus.COMPLEX_COVARIANCE
    #    return g, pvalue, n, n_indep, p_i_best, p_i_worst, None, None, status

    cutoff = context.get_cutoff(matrix)
    _d = {tissue_labels[i]:zscores[i] for i in xrange(0, len(tissue_labels))}
    zscores = array([_d[l] for l in labels])
    inv, n_indep, eigen = Math.capinv(matrix, cutoff, context.epsilon)

    max_z = numpy.max(numpy.abs(zscores))
    p_i_best = 2*stats.norm.cdf(-max_z)
    min_z = numpy.min(numpy.abs(zscores))
    p_i_worst = 2*stats.norm.cdf(-min_z)

    #TODO: implement a better heuristic
    eigen_w, eigen_v = numpy.linalg.eig(inv)
    if numpy.max(eigen_w) > 1e10:
        logging.log(8, "gene %s has a suspicious covariance, skipping", gene)
        status = CalculationStatus.SINGULAR_COVARIANCE
        return g, pvalue, n, n_indep, p_i_best, p_i_worst, eigen_max, eigen_min, status

    w = float(dot(dot(zscores, inv), zscores))
    chi2_p = stats.chi2.sf(w, n_indep)

    # if we got to this point, we are  ok-ish. The chi distribution might have been unable to calculate the pvalue because it is too small...
    if chi2_p == 0:
        status = CalculationStatus.INSUFFICIENT_NUMERICAL_RESOLUTION
    else:
        status = CalculationStatus.OK

    pvalue = chi2_p

    return g, pvalue, n, n_indep, p_i_best, p_i_worst, eigen_max, eigen_min, status

def format_results(results):
    columns = ["gene", "pvalue", "n", "n_indep", "p_i_best", "p_i_worst", "eigen_max", "eigen_min", "status"]
    results = Utilities.to_dataframe(results, columns)
    results = results.sort_values(by="pvalue")
    results = results.fillna("NA")
    return results