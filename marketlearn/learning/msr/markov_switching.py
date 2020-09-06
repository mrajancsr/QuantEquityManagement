"""Module Implements Markov Switching Regression"""

import numpy as np
from scipy.linalg import solve_triangular
from sklearn.preprocessing import PolynomialFeatures


class MarkovSwitchingRegression:
    def __init__(self, degree: int = 1, regime: int = 2, fit_intercept=True):
        self.degree = degree
        self.regime = regime
        self.fit_intercept = fit_intercept

    def _sigmoid(self, z: np.ndarray) -> np.ndarray:
        """Computes the sigmoid function

        :param z: intial guess for optimization
        :type z: np.ndarray
        :return: transition probabilities
        :rtype: np.ndarray
        """
        return 1.0 / (1 + np.exp(-z))

    def _make_polynomial(self, X: np.ndarray) -> np.ndarray:
        bias = self.fit_intercept
        degree = self.degree
        pf = PolynomialFeatures(degree=degree, include_bias=bias)
        return pf.fit_transform(X)

    def _linear_solve(self, A: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Linear solves equation Ax = b

        :param A: design matrix
        :type A: np.ndarray
        :param b: response variable
        :type b: np.ndarray
        :return: x in Ax = b
        :rtype: np.ndarray
        """
        M = np.linalg.cholesky(A.T @ A)
        v = solve_triangular(M, A.T @ b, lower=True)
        return solve_triangular(M.T, v)

    def _beta(self,
              s: int,
              params1: np.ndarray,
              params2: np.ndarray,
              ) -> np.ndarray:
        """Computes the beta of Markov Switching process

        :param s: the state variable, 0 or 1
        :type s: int
        :param params1: parameters corresponding to state 0
        :type params1: np.ndarray, shape = (n_samples,)
        :param params2: parameters corresponding to state 1
        :type params2: np.ndarray
        :raises ValueError: if state is not 0 or 1
        :return: state parameter betas
        :rtype: np.ndarray
        """
        if s not in (0, 1):
            raise ValueError("state regime not supported")
        return params1 if s == 0 else params2

    def _var(self, s: int, var1: float, var2: float) -> float:
        """Returns variance of Markov Switching process

        :param s: state variable, 0 or 1
        :type s: int
        :param var1: variance corresponding to state 0
        :type var1: float
        :param var2: variance corresponding to state 1
        :type var2: float
        :raises ValueError: if state is not 0 or 1
        :return: variance corresponding to regime
        :rtype: float
        """
        if s not in (0, 1):
            raise ValueError("state regime not supported")
        return var1 if s == 0 else var2

    def _normpdf(self,
                 s: int,
                 xt: np.ndarray,
                 yt: np.ndarray,
                 guess: np.ndarray,
                 ) -> np.ndarray:
        """Computes normal density at time t corresponding to regime at state s

        :param s: state variable
        :type s: int
        :param xt: design observation with p features
        :type xt: np.ndarray
        :param yt: response variable at time t
        :type yt: np.ndarray
        :param guess: parameters of msr
         given in following format
         (beta0, beta1, var0, var1)
        :type guess: np.ndarray
        :return: normal density at time t
        :rtype: np.ndarray
        """
        params1 = guess[:4]
        params2 = guess[4:-2]
        beta = self._beta(s, params1[:2], params1[2:])
        var = self._var(s, params2[0], params2[1])
        self.beta = beta
        self.var = var
        self.xt = xt
        self.yt = yt

        exponent = (yt - xt @ beta) ** 2
        exponent /= (-2.0 * var)
        denom = np.sqrt(2 * np.pi * var)
        return exponent / denom

    def _loglikelihood(self,
                       X: np.ndarray,
                       y: np.ndarray,
                       theta: np.ndarray,
                       ) -> np.float64:
        """returns loglikelihood of two state markov
           switching model

        :param X: design matrix
        :type X: np.ndarray, shape = (n_samples, p_features)
        :param y: response variable
        :type y: np.ndarray, shape = (n_samples,)
        :param thetas: parameters of msr given by:
         (beta00, beta01, beta10, beta11, var0, var1, p, q)
        :type theta: np.ndarray
        :return: log-likelihood function value
        :rtype: float
        """
        # step 1; initiate starting values
        n_samples = X.shape[0]
        hfilter = np.zeros((n_samples, self.regime))
        eta_t = np.zeros((n_samples, self.regime))
        predictions = np.zeros((n_samples, self.regime))

        # create transition matrix
        pii, pjj = self._sigmoid(theta[-2:])
        P = self._transition_matrix(pii, pjj)

        # linear solve to start the filter
        ones = np.ones(2)[:, np.newaxis]
        A = np.concatenate((ones - P, ones.T))
        b = np.zeros(self.regime + 1)
        b[-1] = 1
        hfilter[0] = self._linear_solve(A, b)
        predictions[0] = P @ hfilter[0]

        # compute the density at time 0
        densities = np.zeros(self.regime)
        cond_density = np.zeros(n_samples)
        densities[0] = self._normpdf(0, X[0], y[0], theta)
        densities[1] = self._normpdf(1, X[0], y[0], theta)
        eta_t[0] = densities

        # step2: start the filter
        for t in range(1, n_samples):
            exponent = predictions[t-1] * eta_t[t]
            loglik = exponent.sum()
            cond_density[t] = loglik
            hfilter[t] = exponent / loglik
            predictions[t] = P @ hfilter[t]
            densities[0] = self._normpdf(0, X[t], y[t], theta)
            densities[1] = self._normpdf(1, X[t], y[t], theta)
            eta_t[t] = densities

        # calculate the loglikelihood
        return np.log(cond_density).mean()

    def _objective_func(self,
                        guess: np.ndarray,
                        X: np.ndarray,
                        y: np.ndarray) -> np.float64:
        """the objective function to be minimized

        :param guess: parameters for optimization
        :type guess: np.ndarray
        :param X: design matrix
        :type X: np.ndarray
        :param y: response variable
        :type y: np.ndarray
        :return: scaler value from minimization
        :rtype: np.float64
        """
        f = self._loglikelihood(X, y, theta=guess)
        return -f

    def _transition_matrix(self, pii: float, pjj: float) -> np.ndarray:
        """Constructs the transition matrix given the diagonal probabilities

        :param pii: probability that r.v
         stays at state i given it starts at i
         given by first element of diagonal
        :type pii: float
        :param pjj: probability that r.v
         stays at state j given it starts at j
         given by next element of diagonal
        :type pjj: float
        :return: transition matrix
        :rtype: np.ndarray
        """
        transition_matrix = np.zeros((2, 2))
        transition_matrix[0, 0] = pii
        transition_matrix[0, 1] = 1 - pii
        transition_matrix[1, 1] = pjj
        transition_matrix[1, 0] = 1-pjj
        return transition_matrix

    def fit(self, X: np.ndarray, y: np.ndarray) -> "MarkovSwitchingRegression":
        """fits two state markov-switching

        :param X: design matrix
        :type X: np.ndarray,
         shape = (n_samples, p_features)
        :param y: response variable
        :type y: np.ndarray,
         shape = (n_samples,)
        :return: fitted parameters to data
         param_shape = 2 * (bias + p_features) * k_regimes
        :rtype: MarkovSwitchingRegression
        """
        p_features = X.shape[1]
        X = self._make_polynomial(X)

        # total parameters to be estimated
        # estimate bias, slope, variances for two regimes and transition prob
        bias = self.fit_intercept
        k = 2 * (bias + p_features) * self.regime
        params = np.array([0.2, 0.3, 0.4, 0.6, y.var(ddof=1), X.var(ddof=1), 0.5, 0.5])
        prob = self._filtered_probabalities(X, y, params)
        return prob
