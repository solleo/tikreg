import numpy as np
from scipy.stats import zscore






def hrf_default_basis(dt=2.0, duration=32):
    '''

    Returns
    --------
    hrf_basis (time-by-3)
    '''
    try:
        import hrf_estimation as he
    except ImportError as err:
        issue = '''You need to install `hrf_estimation` package: "pip install -U hrf_estimation"'''
        err.message = err.message + issue
        raise

    time = np.arange(0, duration, dt)
    h1 = he.hrf.spm_hrf_compat(time)
    h2 = he.hrf.dspmt(time)
    h3 = he.hrf.ddspmt(time)

    hrf_basis = np.c_[h1, h2, h3]
    return hrf_basis



def fast_indexing(a, rows, cols=None):
    '''
    Much faster than fancy indexing for taking
    selected rows and cols from matrix.
    Slightly faster for row indexing, too

    '''
    if cols is None:
        cols = np.arange(a.shape[-1])
    idx = rows.reshape(-1,1)*a.shape[1] + cols
    return a.take(idx)



def determinant_normalizer(mat, thresh=1e-08):
    '''get the (pseudo-) determinant of the matrix
    '''
    evals = np.linalg.eigvalsh(mat)
    gdx = evals > thresh
    det = np.prod(evals[gdx])
    return det**(1./gdx.sum())



def delay2slice(delay):
    if delay > 0:
        ii = slice(None, -delay)
    elif delay == 0:
        ii = slice(None, None)
    elif delay < 0:
        raise ValueError('No negative delays')
    return ii


def generate_data(n=100, p=10, v=2,
                  noise=1.0,
                  testsize=0,
                  dozscore=False,
                  feature_sparsity=0.0):
    '''Get some B,X,Y data generated from gaussian (0,1).

    Parameters
    ----------
    n (int): Number of samples
    p (int): Number of features
    v (int): Number of responses
    noise (float): Noise level
    testsize (int): samples in validation set
    dozscore (bool): z-score features and responses?
    feature_sparsity (float in 0-1):
        number of irrelevant features as
        percentage of total

    Returns
    -------
    B (p-by-v np.ndarray):
        True feature weights
    (Xtrain, Xval):
        Feature matrix for training and validation
        Xval is optional and contains no noise
    (Ytrain, Yval):
        Response matrix for training and validation
        Yval is optional and contains no noise

    Examples
    --------
    >>> B, X, Y = generate_data(n=100, p=10, v=2,noise=1.0,testsize=0)
    >>> B.shape, X.shape, Y.shape
    ((10, 2), (100, 10), (100, 2))
    >>> B, (Xtrn, Xval), (Ytrn, Yval) = generate_data(n=100, p=10, v=2,testsize=20)
    >>> B.shape, Xval.shape, Yval.shape
    ((10, 2), (20, 10), (20, 2))
    '''
    X = np.random.randn(n, p)
    B = np.random.randn(p, v)
    if dozscore: X = zscore(X)
    nzeros = int(feature_sparsity*p)
    if nzeros > 0:
        B[-nzeros:,:] = 0

    Y = np.dot(X, B)
    Y += np.random.randn(*Y.shape)*noise
    if dozscore: Y = zscore(Y)

    if testsize:
        Xval = np.random.randn(testsize, p)
        if dozscore:
            Xval = zscore(Xval)
        Yval = np.dot(Xval, B)
        if dozscore: Yval = zscore(Yval)
        return B, (X,Xval), (Y, Yval)

    return B, X,Y


def mult_diag(d, mtx, left=True):
    """
    Multiply a full matrix by a diagonal matrix.
    This function should always be faster than dot.

    Parameters
    ----------
    d [1D (N,) array]
         contains the diagonal elements
    mtx [2D (N,N) array]
         contains the matrix

    Returns
    --------
    res (N, N)
         Result of multiplying the matrices

    Notes
    ------
    This code by:
    Pietro Berkes berkes@gatsby.ucl.ac...
    Mon Mar 26 11:55:47 CDT 2007
    http://mail.scipy.org/pipermail/numpy-discussion/2007-March/026807.html

    mult_diag(d, mts, left=True) == dot(diag(d), mtx)
    mult_diag(d, mts, left=False) == dot(mtx, diag(d))


    """
    if left:
        return (d*mtx.T).T
    else:
        return d*mtx




def noise_ceiling_correction(repeats, yhat, dozscore=True):
    """Noise ceiling corrected correlation coefficient.

    Parameters
    ----------
    repeats: np.ndarray, (nreps, ntpts, nsignals)
        The stimulus timecourses for each repeat.
        Each repeat is `ntpts` long.
    yhat: np.ndarray, (ntpts, nsignals)
        The predicted timecourse for each signal.
    dozscore: bool
        This algorithm only works correctly if the
        `repeats` and `yhat` timecourses are z-scored.
        If these are already z-scored, set to False.

    Returns
    -------
    r_ns: np.ndarray, (nsignals)
        The noise ceiling corrected correlation coefficient
        for each of the signals. One may square this result
        (while keeping the sign) to obtain the
        'explainable variance explained.'

    Notes
    -----
    $r_{ns}$ is misbehaved if $R^2$ is very low.

    References
    ----------
    Schoppe, et al. (2016), Hsu, et al. (2004), David, et al. (2005).
    """
    ntpts = repeats.shape[1]
    reps = zscore(repeats, 1) if dozscore else repeats
    yhat = zscore(yhat, 0) if dozscore else yhat

    R2 = explainable_variance(reps, ncorrection=True, dozscore=False)
    ymean = reps.mean(0)
    ycov = (ymean*yhat).sum(0)/(ntpts - 1) # sample covariance
    return ycov/np.sqrt(R2)


def explainable_variance(repeats, ncorrection=True, dozscore=True):
    '''Compute the explainable variance in the recorded signals.

    This can be interpreted as the R^2 of a model that predicts
    each repetition with the mean across repetitions.

    Parameters
    ----------
    repeats: np.ndarray, (nreps, ntpts, nsignals)
        The timecourses for each stimulus repetition.
        Each of repeat is `ntpts` long.
    ncorrection: bool
        Bias correction for number of repeats.
        Equivalent to computing the adjusted R^2.
    dozscore: bool
        This algorithm only works with z-scored repeats. If
        the each repetition is already z-scored, set to False.

    Returns
    -------
    EV: np.ndarray (nsignals)
        The explainable variance computed across repeats.
        Equivalently, the (adjusted) R^2 value.
    '''
    repeats = zscore(repeats, 1) if dozscore else repeats
    residual = repeats - repeats.mean(0)
    residualvar = np.mean(residual.var(1), 0)
    ev = 1 - residualvar

    if ncorrection:
        ev = ev - ((1 - ev) / np.float((repeats.shape[0] - 1)))
    return ev


def absmax(arr):
    return max(abs(np.nanmin(arr)), abs(np.nanmax(arr)))


def delay_signal(data, delays=[0, 1, 2, 3], fill=0):
    '''
    >>> x = np.arange(6).reshape(2,3).T + 1
    >>> x
    array([[1, 4],
           [2, 5],
           [3, 6]])
    >>> delay_signal(x, [-1,2,1,0], fill=0)
    array([[2, 5, 0, 0, 0, 0, 1, 4],
           [3, 6, 0, 0, 1, 4, 2, 5],
           [0, 0, 1, 4, 2, 5, 3, 6]])
    >>> delay_signal(x, [-1,2,1,0], fill=np.nan)
    array([[  2.,   5.,  nan,  nan,  nan,  nan,   1.,   4.],
           [  3.,   6.,  nan,  nan,   1.,   4.,   2.,   5.],
           [ nan,  nan,   1.,   4.,   2.,   5.,   3.,   6.]])
    '''
    if data.ndim == 1:
        data = data[...,None]
    n, p = data.shape
    out = np.ones((n, p*len(delays)), dtype=data.dtype)*fill

    for ddx, num in enumerate(delays):
        beg, end = ddx*p, (ddx+1)*p
        if num == 0:
            out[:, beg:end] = data
        elif num > 0:
            out[num:, beg:end] = data[:-num]
        elif num < 0:
            out[:num, beg:end] = data[abs(num):]
    return out


def whiten_penalty(X, penalty=0.0):
    '''Whiten features (p)
    X (n, p) (e.g. time by features)
    '''
    cov = np.cov(X.T)
    u, s, ut = np.linalg.svd(cov, full_matrices=False)
    covnegsqrt = np.dot(mult_diag((s+penalty)**(-1/2.0), u, left=False), ut)
    return np.dot(covnegsqrt, X.T).T



def columnwise_correlation(y, ypred, zscorea=True, zscoreb=True, axis=0):
    r'''Compute correlations efficiently

    Examples
    --------
    >>> x = np.random.randn(100,2)
    >>> y = np.random.randn(100,2)
    >>> cc = columnwise_correlation(x, y)
    >>> cc.shape
    (2,)
    >>> c1 = np.corrcoef(x[:,0], y[:,0])[0,1]
    >>> c2 = np.corrcoef(x[:,1], y[:,1])[0,1]
    >>> assert np.allclose(cc, np.r_[c1, c2])

    Notes
    -----
    Recall that the correlation cofficient is defined as

    .. math::
       \rho_{x, y} = \frac{cov(X,Y)}{var(x)var(y)}

    Since it is scale invariant, we can zscore and get the same

    .. math::
       \rho_{x, y} = \rho_{zscore(x), zscore(y)} = \frac{cov(X,Y)}{1*1} =
       \frac{1}{N}\frac{\sum_i^n \left(x_i - 0 \right) \left(y_i - 0 \right)}{1*1} =
       \frac{1}{N}\sum_i^n \left(x_i * y_i \right)
    '''
    if zscorea:
        y = zscore(y, axis=axis)
    if zscoreb:
        ypred = zscore(ypred, axis=axis)
    corr = (y * ypred).mean(axis=axis)
    return corr




def generate_trntest_folds(N, sampler='cv', testpct=0.2, nchunks=5, nfolds=5):
    '''
    N : int
        The number of samples in the training set
    samplers : str
        * cv: `nfolds` for cross-validation
        * bcv: `nfolds` is a tuple of (nrepeats, nfolds)
               for repeated cross-validation.
    '''
    oN = N
    ntrain = int(N - N*(testpct))
    samples = np.arange(N)
    step = 1 if sampler == 'mbb' else nchunks
    samples = [samples[idx:idx+nchunks] for idx in xrange(0,N-nchunks+1, step)]
    samples = map(list, samples)
    N = len(samples)
    append = lambda z: reduce(lambda x, y: x+y, z)
    allidx = np.arange(oN)
    if sampler == 'cv':
        np.random.shuffle(samples)
        sets = np.array_split(np.arange(len(samples)), nfolds)
        for i,v in enumerate(sets):
            test = np.asarray(append([samples[t] for t in v]))
            train = allidx[~np.in1d(allidx, test)]
            yield train, test
    elif sampler == 'bcv':
        # Repeat the cross-validation N times
        assert isinstance(nfolds, tuple)
        reps, nfolds = nfolds
        for rdx in xrange(reps):
            np.random.shuffle(samples)
            sets = np.array_split(np.arange(len(samples)), nfolds)
            for i,v in enumerate(sets):
                test = np.asarray(append([samples[t] for t in v]))
                train = allidx[~np.in1d(allidx, test)]
                yield train, test

    elif sampler == 'nbb' or sampler == 'mbb':
        fun = lambda x: [x[t] for t in np.random.randint(0, N, ntrain/nchunks)]
        for bdx in xrange(nfolds):
            train = np.asarray(append(fun(samples)))
            test = allidx[~np.in1d(allidx, train)]
            yield train, test


def test_generators(N=100, testpct=0.2, nchunks=5, nfolds=5):
    ntest = int(N*(1./nfolds))
    ntrain = N - ntest
    alltrn = []
    folds = generate_trntest_folds(N, 'cv', testpct=testpct, nfolds=nfolds, nchunks=nchunks)
    for idx, (trn, val) in enumerate(folds):
        # none of the trn is in the val
        assert np.in1d(trn, val).sum() == 0
        assert np.in1d(val, trn).sum() == 0
        assert len(np.unique(np.r_[val, trn])) == N
        assert ntrain + nchunks >= len(trn) >= ntrain - nchunks

    ntest = int(N*testpct)
    ntrain = int(np.ceil(N - ntest))
    remainder = np.mod(ntrain, nchunks)
    nfolds = 10
    folds = generate_trntest_folds(N, 'nbb', nfolds=nfolds, testpct=testpct, nchunks=nchunks)
    for idx, (trn, val) in enumerate(folds):
        # none of the trn is in the val
        assert np.in1d(trn, val).sum() == 0
        assert np.in1d(val, trn).sum() == 0
        assert (len(trn) == ntrain - remainder) or (len(trn) == ntrain - nchunks)
    assert idx+1 == nfolds

    nfolds = 100
    folds = generate_trntest_folds(N, 'mbb', nfolds=nfolds, testpct=testpct, nchunks=nchunks)
    for idx, (trn, val) in enumerate(folds):
        # none of the trn is in the val
        assert np.in1d(trn, val).sum() == 0
        assert np.in1d(val, trn).sum() == 0
        assert len(trn) == (ntrain - remainder) or (len(trn) == ntrain - nchunks)
    assert idx+1 == nfolds


def fast_indexing(a, rows, cols=None):
    '''
    Much faster than fancy indexing for taking
    selected rows and cols from matrix.
    Slightly faster for row indexing, too

    '''
    if cols is None:
        cols = np.arange(a.shape[-1])
    idx = rows.reshape(-1,1)*a.shape[1] + cols
    return a.take(idx)


def test_fast_indexing():
    D = np.random.randn(1000, 1000)
    rows = np.random.randint(0, 1000, (400))
    cols = np.random.randint(0, 1000, (400))

    a = fast_indexing(D, rows, cols)
    b = D[rows, :][:, cols]
    assert np.allclose(a, b)
    a = fast_indexing(D, rows)
    b = D[rows, :]
    assert np.allclose(a, b)
    a = fast_indexing(D.T, cols).T
    b = D[:, cols]
    assert np.allclose(a, b)


def test_noise_ceiling_correction():
    '''Based on Schoppe, et al. (2016)'''
    # Author's Sample MATLAB code
    # https://github.com/OSchoppe/CCnorm/blob/master/calc_CCnorm.m
    from scipy.stats import zscore
    signal = np.random.randn(50)
    repeats = np.asarray([signal + np.random.randn(len(signal))*1. for t in xrange(10)])
    nreps, ntpts = repeats.shape

    repeats = zscore(repeats, 1)
    ymean = np.mean(repeats,0) # mean time-course
    yhat = zscore(ymean + np.random.randn(len(ymean))*0.5)

    Vy = np.var(ymean)
    Vyhat = 1.
    Cyyhat = np.cov(ymean, yhat)[0,1]
    mcov = ((ymean - ymean.mean(0))*yhat).sum(0)/(ntpts - 1) # sample covariance
    assert np.allclose(Cyyhat, mcov)

    top = np.var(np.sum(repeats,0)) - np.sum(np.var(repeats, 1))
    SP = top/(nreps*(nreps-1)) # THIS IS EXPLAINABLE VARIANCE
    # same as
    top2 = (nreps**2)*np.var(np.mean(repeats,0)) - nreps
    SP2 = top2/(nreps*(nreps -1))
    assert np.allclose(top, top2)
    assert np.allclose(SP, SP2)
    # same as
    top3 = nreps*np.var(np.mean(repeats,0)) - 1
    SP3 = top3/(nreps-1)
    assert np.allclose(top2/nreps, top3)
    assert np.allclose(SP2, SP3)
    # same as
    ev = np.var(np.mean(repeats,0)) # same as R2 := SSreg/SStot
    ev = ev - ((1 - ev) / np.float((repeats.shape[0] - 1))) # adjusted
    assert np.allclose(ev, SP)
    # same as (1 - residual variance)
    assert np.allclose(explainable_variance(repeats[...,None],
                                            dozscore=False, ncorrection=True),
                       SP)
    assert np.allclose(explainable_variance(repeats[...,None],
                                            dozscore=True, ncorrection=True),
                       SP)
    # measures
    CCabs	= Cyyhat/np.sqrt(Vy*Vyhat)
    CCnorm	= Cyyhat/np.sqrt(SP*Vyhat)
    CCmax	= np.sqrt(SP/Vy)
    corrected = CCabs/CCmax
    eqn27 = Cyyhat/np.sqrt(SP) # eqn 27 from Schoppe, et al. (2016) paper

    res = noise_ceiling_correction(repeats, yhat, dozscore=True)
    assert np.allclose(eqn27, res)
    assert np.allclose(corrected, res)
    assert np.allclose(CCnorm, res)