import numpy as np


def _steps(p, h0, factor, maxiter):
    h = p * h0
    if h == 0:
        h = h0
    return h * factor ** np.arange(maxiter)


def _central(f, x, i, h, args):
    xp = x.copy()
    xm = x.copy()
    xp[i] += h
    xm[i] -= h
    return (f(xp, *args) - f(xm, *args)) * (0.5 / h)


def jacobi(
    f,
    x,
    *args,
    mask=None,
    rtol=0,
    maxiter=10,
    maxgrad=3,
    step=(0.125, 0.5),
    diagnostic=None,
):
    assert maxiter > 0
    assert maxgrad >= 0
    assert 0 < step[0] < 1
    assert 0 < step[1] < 1

    squeeze = np.ndim(x) == 0
    x = np.atleast_1d(x).astype(float)
    assert x.ndim == 1

    x_indices = np.arange(len(x))
    if mask is not None:
        mask = np.asarray(mask, dtype=bool)
        x_indices = x_indices[mask]

    if isinstance(diagnostic, dict):
        diagnostic.clear()
        diagnostic["iteration"] = np.zeros(len(x_indices), dtype=np.uint8)

    nx = len(x_indices)
    for ik, k in enumerate(x_indices):
        h = _steps(x[k], *step, maxiter)

        r = _central(f, x, k, h[0], args)
        r_shape = np.shape(r)
        r = np.reshape(r, -1)
        nr = len(r)
        re = np.full(nr, np.inf)
        todo = np.ones(nr, dtype=bool)
        fd = [r]

        if ik == 0:
            jac = np.empty(r_shape + (nx,), dtype=r.dtype)
            err = np.empty(r_shape + (nx,), dtype=r.dtype)

            if diagnostic:
                diagnostic["call"] = np.full((nr, nx), 2, dtype=np.uint8)

        for i in range(1, len(h)):
            fdi = np.reshape(_central(f, x, k, h[i], args), -1)
            fd.append(fdi if i == 1 else fdi[todo])
            if diagnostic:
                diagnostic["call"][todo, ik] += 2
                diagnostic["iteration"][ik] += 1

            # polynomial fit with one extra degree of freedom
            grad = min(i - 1, maxgrad)
            start = i - (grad + 1)
            stop = i + 1
            q, c = np.polyfit(
                h[start:stop] ** 2, fd[start:], grad, rcond=None, cov=True
            )
            ri = q[-1]
            # pulls have roughly unit variance, however,
            # the pull distribution is not gaussian and looks
            # more like student's t
            rei = c[-1, -1] ** 0.5

            # update estimates that have significantly smaller error
            sub_todo = rei < re[todo]
            todo1 = todo.copy()
            todo[todo1] = sub_todo
            r[todo] = ri[sub_todo]
            re[todo] = rei[sub_todo]

            # do not improve estimates further which meet the tolerance
            if rtol > 0:
                sub_todo &= rei > rtol * np.abs(ri)
                todo[todo1] = sub_todo

            if np.sum(todo) == 0:
                break

            # shrink previous vectors of estimates
            fd = [fdi[sub_todo] for fdi in fd]

        jac[..., ik] = r.reshape(r_shape)
        err[..., ik] = re.reshape(r_shape)

    if diagnostic:
        diagnostic["call"].shape = r_shape + (nx,)

    if squeeze:
        if diagnostic:
            diagnostic["call"] = np.squeeze(diagnostic["call"])
        jac = np.squeeze(jac)
        err = np.squeeze(err)

    return jac, err
