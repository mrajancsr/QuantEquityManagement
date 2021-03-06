"""
Implementation of Harry Markowitz's Modern Portfolio Theory
Author: Rajan Subramanian
Created Feb 10 2021
"""

from __future__ import annotations
from marketlearn.portfolio import Asset
from numpy import diag, fromiter, sqrt
from numpy.random import random
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# import plotly.graph_objects as go


class Harry:
    """
    Implements Harry Markowitz'a Model of mean variance optimization
    Parameters
    ----------
    historical_prices : pd.DataFrame
        represents historical daily end of day prices
    Attributes
    ----------
    assets: Dict[name: Asset]
        dictionary of Asset objects whose keys are asset names
    covariance_matrix: np.ndarray
        Scaled Covariance Matrix of daily log returns
    asset_expected_returns: np.ndarray
        forecasted sample means of each Asset
    asset_expected_vol: np.ndarray
        forecasted sample volatility of each Asset
    """

    def __init__(self, historical_prices: pd.DataFrame, risk_free_rate=None):
        """Default constructor used to initialize portfolio"""
        self.__assets = {
            name: Asset(name=name, price_history=historical_prices[name])
            for name in historical_prices.columns
        }
        self.covariance_matrix = Asset.covariance_matrix(tuple(self))
        self.asset_expected_returns = fromiter(
            self.asset_expected_returns(), dtype=float
        )
        self.asset_expected_vol = fromiter(
            self.asset_expected_volatility(), dtype=float
        )

        self.security_count = len(self.__assets)
        self.risk_free_rate = risk_free_rate

    def __eq__(self, other: Harry):
        return type(self) is type(other) and self.assets() == other.assets()

    def __ne__(self, other: Harry):
        return not (self == other)

    def __repr__(self):
        return f"Portfolio size: {self.security_count} Assets"

    def __iter__(self):
        yield from self.__assets.values()

    def assets(self):
        yield from self

    def get_asset(self, name: str) -> Asset:
        """return the Asset in portfolio given name
        Parameters
        ----------
        name : str
            name of the Asset
        Returns
        -------
        Asset
            contains information about the asset
        """
        return self.__assets[name]

    def asset_expected_returns(self):
        """gets expected return of each asset in portfolio
        Yields
        -------
        Iterator[float]
            an iteration of expected return of each asset in portfolio
        """
        yield from (asset.expected_returns for asset in self)

    def asset_expected_volatility(self):
        """gets expected volatility of each asset in portfolio
        Yields
        -------
        Iterator[float]
            iteration of expected vol of each asset scaled by trading days
        """
        yield from sqrt(diag(self.covariance_matrix))

    @classmethod
    def random_weights(cls, nsim: int, nsec: int):
        """creates a portfolio with random weights
        Parameters
        ----------
        nsec : int
            number of securities in porfolio
        nsim : int, optional, default=1
            number of simulations to perform
        Returns
        -------
        np.ndarray, shape=(nsim, nsec)
            random weight matrix
        """
        if nsim == 1:
            weights = random(nsec)
            weights /= weights.sum()
        else:
            weights = random((nsim, nsec))
            weights = (weights.T / weights.sum(axis=1)).T

        return weights

    def portfolio_variance(self, weights: np.ndarray):
        """computes the portfolio variance
        portfolio variance is given by var_p = w'cov(R)w
        Parameters
        ----------
        weights : np.ndarray, shape=(n_assets,), (n_grid, n_assets)
            weight of each asset in portfolio
            n_assets is number of assets in portfolio
            for efficient portfolio, assumes each row
            is a linear combination of grid of two weights
            where one asset is the minimum variance portfolio
            and the other is the markovitz portfolio
        Returns
        -------
        float
            portfolio variance
        """
        ndim = weights.ndim
        if ndim == 1:
            return weights.T @ self.covariance_matrix @ weights
        else:
            return diag(weights @ self.covariance_matrix @ weights.T)

    def portfolio_expected_return(self, weights: np.ndarray):
        ndim = weights.ndim
        if ndim == 1:
            return weights.T @ self.asset_expected_returns
        # allows construction of efficient portfolios
        else:
            return weights @ self.asset_expected_returns

    def simulate_investment_opportunity_set(self, nportfolios: int):
        """runs a monte-carlo simulation by generating random portfolios

        The random portfolios are generated by first generating random
        weights and computing the standard deviation and expected returns of
        portfolio in each simulation.  The resultant pair of points given by
        (sig_i(p), mu_i(p)) is what is plotted

        Parameters
        ----------
        nsec : int
            [description]
        nportfolios : int, optional
            [description], by default 1
        """
        nsec = self.security_count
        weights = Harry.random_weights(nsim=nportfolios, nsec=nsec)

        # return volatility and mean of each simulation as a tuple
        return (
            (
                np.sqrt(self.portfolio_variance(weights[p])),
                self.portfolio_expected_return(weights[p]),
            )
            for p in range(nportfolios)
        )

    def graph_simulated_portfolios(self, nportfolios: int):
        """plots the simulated portfolio
        Parameters
        ----------
        nportfolios : int
            [description]
        """
        simulations = self.simulate_investment_opportunity_set(nportfolios)
        xval, yval = zip(*simulations)

        plt.scatter(xval, yval, marker="o", s=10, cmap="winter", alpha=0.35)

        # Uncomment the area below for plotly graph objects

        """
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=xval,
                y=yval,
                mode="markers",
                line=dict(color="rgb(55, 83, 109)", dash="dash"),
            )
        )
        fig.update_layout(
            title_text="Simulated Portfolio Frontier",
            template="plotly_white",
            xaxis=dict(title="Annualized portfolio expected volatility"),
            yaxis=dict(title="Annualized portfolio expected returns"),
        )
        fig.show()"""

    def sharpe_ratio(self, weights: np.ndarray) -> float:
        """Comoputes the sharpe ratio of portfolio given weights
        Parameters
        ----------
        weights : np.ndarray
            percentage of each asset held in portfolio
        Returns
        -------
        sharpe ratio
            float
        """
        return (
            self.portfolio_expected_return(weights) - self.risk_free_rate
        ) / np.sqrt(self.portfolio_variance(weights))

    def optimize_risk(
        self, constraints: bool = False, target: float = None, bounds=None
    ):
        """Computes the weights corresponding to minimum variance
        Parameters
        ----------
        constraints : bool, optional, default=False
            mean constraint
        target : float, optional, default=None
            target portfolio return if constraints is True
        Returns
        -------
        np.ndarray
            weights corresponding to minimum variance
        """
        # get count of assets in portfolio
        total_assets = self.security_count

        # make random guess
        guess_weights = Harry.random_weights(nsim=1, nsec=total_assets)

        # minimize risk subject to target level of return constraint
        if constraints:
            consts = [
                {
                    "type": "eq",
                    "fun": lambda w: self.portfolio_expected_return(w)
                    - target,
                },
                {"type": "eq", "fun": lambda w: sum(w) - 1},
            ]
        # minimize risk with only contraint sum of weights = 1
        else:
            consts = [{"type": "eq", "fun": lambda w: sum(w) - 1}]

        # minimize the portolio variance, assume no short selling
        weights = minimize(
            fun=lambda w: self.portfolio_variance(w),
            x0=guess_weights,
            constraints=consts,
            method="SLSQP",
            bounds=bounds,
        )["x"]
        return weights

    def optimize_sharpe(self, bounds=None):
        """Return the weights corresponding to maximizing sharpe ratio
        The sharpe ratio is given by SRp = mu_p - mu_f / sigma_p
        subject to w'mu = mu_p
                   w'cov(R)w = var_p
                   s.t sum(weights) = 1
        """
        # get count of assets in portfolio
        total_assets = self.security_count

        # make random guess
        guess_weights = Harry.random_weights(nsim=1, nsec=total_assets)

        # set target return & target variance and sum of weights constraint
        consts = [{"type": "eq", "fun": lambda w: sum(w) - 1}]

        # maximize sharpe subject to above constraints
        weights = minimize(
            fun=lambda w: -1 * self.sharpe_ratio(w),
            x0=guess_weights,
            constraints=consts,
            method="SLSQP",
            bounds=bounds,
        )["x"]

        return weights

    def construct_efficient_frontier(self, bounds=None):
        """Constructs the efficient frontier

        Parameters
        ----------
        bounds : [type], optional, default=None
            bound for each asset weight
            for long position, bound is (0, 1)
            for short position, bound is (-1, 0)

        Returns
        -------
        tuple
            efficient portfolio's volatility and expected returns
        """
        # get minimum variance portfolio
        m = self.optimize_risk(bounds=bounds)

        # compute mean of global minimum variance portfolio
        minimum_var_portfolio_mean = self.portfolio_expected_return(m)

        # get efficient portfolio x whose target return is max security returns
        target = self.asset_expected_returns.max()
        x = self.optimize_risk(constraints=True, target=target, bounds=bounds)

        # compute grid of values
        theta = np.linspace(-1, 1, 1000)

        # portfolio z is linear combination of above two portfolios
        z = theta[:, np.newaxis] * m + (1 - theta[:, np.newaxis]) * x

        # compute portfolio mean and variance with above weights
        efficient_portfolio_mean = self.portfolio_expected_return(z)
        efficient_portfolio_var = self.portfolio_variance(z)

        # get the max volatility of assets in universe
        vol = self.asset_expected_vol.max()

        # return pair of mean returns and vol for new efficient portfolio
        mu_p = efficient_portfolio_mean[
            efficient_portfolio_mean >= minimum_var_portfolio_mean
        ]
        sig_p = sqrt(
            efficient_portfolio_var[
                efficient_portfolio_mean >= minimum_var_portfolio_mean
            ]
        )

        return sig_p[sig_p <= vol], mu_p[sig_p <= vol]

    def graph_frontier(self, nportfolios: int, bounds=None):
        """graphs the efficient frontier set

        Parameters
        ----------
        nportfolios : int
            [description]
        bounds : [type], optional
            [description], by default None
        """
        plt.figure(figsize=(8, 5))
        self.graph_simulated_portfolios(nportfolios)

        # construct the frontier
        xval, yval = self.construct_efficient_frontier(bounds=bounds)
        plt.plot(xval, yval, color="orange", linewidth=4)
        plt.grid()

    def graph_investment_opportunity_set(self, bounds=None):
        # create grid of target returns > minimum variance portfolio mean
        target_returns = np.linspace(0, 1, 1000)
        # todo: this can be made faster
        weights = map(
            lambda x: self.optimize_risk(
                constraints=True, target=x, bounds=bounds
            ),
            target_returns,
        )
        weights = np.vstack(tuple(weights))

        # get expected returns and vols
        portfolio_expected_returns = self.portfolio_expected_return(weights)
        portfolio_expected_vol = np.sqrt(self.portfolio_variance(weights))

        # plot graph of sig vs expected returns
        plt.figure(figsize=(8, 5))
        plt.plot(
            portfolio_expected_vol,
            portfolio_expected_returns,
            color="black",
            linestyle="-",
        )
        plt.grid()

    def __global_minimum_variance(self, mean_constraint=False, target=None):
        """computes weights associated with global minimum variance

        This function uses the formula for global minimum variance
        # subject to constraint w'1 = 1
        # if mean constraint is true, then another constraint is added
        # w'mu = target
        """
        n = self.size + 1 if mean_constraint is False else self.size + 2
        A = np.zeros((n, n))
        ones = np.ones(self.size)
        b = np.zeros(n)
        A[: self.size, : self.size] = self.covmat * 2
        A[-1, : self.size], A[: self.size, -1] = ones, ones
        if mean_constraint is True:
            A[-2, : self.size], A[: self.size, -2] = self.mu_vec.T, self.mu_vec
            b[-2] = target
        b[-1] = 1
        return np.linalg.solve(A, b)[: self.size]
