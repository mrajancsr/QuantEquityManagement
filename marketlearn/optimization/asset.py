"""Implementation of Asset class"""

from __future__ import annotations
from functools import lru_cache
from numpy import array, cov, isnan, log
from typing import Tuple
import pandas as pd


class Asset:
    """Serves as a composite class to Portfolio Class"""

    all_assets = []

    __TRADING_DAYS_PER_YEAR = 252

    def __init__(self, name: str, price_history: pd.Series):
        """default constructor used to initialize Asset Class"""
        self.name = name
        self.price_history = price_history
        self.size = price_history.shape[0]
        self.returns_history = log(1 + self.price_history.pct_change())
        self.annualized_returns = self.returns_history.sum()
        self.expected_returns = self._get_expected_returns()
        self.__class__.all_assets.append(self)

    def _get_expected_returns(self):
        return Asset.__TRADING_DAYS_PER_YEAR * self.returns_history.mean()

    @staticmethod
    def get_annualization_factor():
        return Asset.__TRADING_DAYS_PER_YEAR

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return f"Asset name: {self.name}, \
        \nexpected returns: {self.expected_returns:.5f}, \
        \nannualized_returns: {self.annualized_returns:.5f}"

    @staticmethod
    @lru_cache
    def covariance_matrix(assets: Tuple[Asset]):
        print("testing this bitch")
        zt = array([a.returns_history - a.expected_returns for a in assets])
        return cov(zt.T[~isnan(zt.T).any(axis=1)], rowvar=False)