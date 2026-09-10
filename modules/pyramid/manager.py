"""Pyramiding and tranche scaling models for position building and derisking."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PyramidModel(Enum):
    """Enumeration of 7 pyramiding and tranche scaling models."""

    NO_PYRAMID = "no_pyramid"
    EQUAL_SPLIT = "equal_split"
    FRONT_LOADED = "front_loaded"
    INVERSE_PYRAMID = "inverse_pyramid"
    MOMENTUM_CONFIRMED = "momentum_confirmed"
    RISK_FREE_RUNNER = "risk_free_runner"
    ADAPTIVE_TRANCHE = "adaptive_tranche"


MODEL_ALIASES = {
    "confirmation_gate": PyramidModel.MOMENTUM_CONFIRMED,
    "momentum_cascade": PyramidModel.ADAPTIVE_TRANCHE,
}


@dataclass
class ScaleInSignal:
    """Represents a scale-in tranche addition instruction."""

    tranche_index: int
    additional_lots: float
    fill_price: float
    move_to_be: bool
    new_sl: Optional[float] = None


@dataclass
class ScaleOutSignal:
    """Represents a scale-out partial close instruction."""

    fraction_to_close: float
    lots_to_close: float
    exit_price: float
    move_to_be: bool
    new_sl: Optional[float] = None


class PyramidManager:
    """Manages tranche allocations, scale-in additions, and scale-out derisking."""

    def __init__(
        self,
        model: Any,
        total_planned_lots: float,
    ) -> None:
        """Initialize pyramid manager with model and total planned lot size.

        Parameters:
            model: PyramidModel enum instance or string identifier.
            total_planned_lots: Full position size planned for the setup.
        """
        if isinstance(model, str):
            clean_str = model.lower()
            if clean_str in MODEL_ALIASES:
                self.model = MODEL_ALIASES[clean_str]
            else:
                try:
                    self.model = PyramidModel(clean_str)
                except ValueError:
                    self.model = PyramidModel.NO_PYRAMID
        else:
            self.model = model

        self.total_planned_lots = total_planned_lots
        self.tranche_shares = self._get_tranche_shares(self.model)
        self.max_tranches = len(self.tranche_shares)

    @staticmethod
    def _get_tranche_shares(model: PyramidModel) -> List[float]:
        if model == PyramidModel.NO_PYRAMID:
            return [1.0]
        if model == PyramidModel.EQUAL_SPLIT:
            return [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
        if model == PyramidModel.FRONT_LOADED:
            return [0.50, 0.30, 0.20]
        if model == PyramidModel.INVERSE_PYRAMID:
            return [0.20, 0.30, 0.50]
        if model == PyramidModel.MOMENTUM_CONFIRMED:
            return [0.50, 0.50]
        if model == PyramidModel.ADAPTIVE_TRANCHE:
            return [0.25, 0.25, 0.25, 0.25]
        if model == PyramidModel.RISK_FREE_RUNNER:
            return [1.0]
        return [1.0]

    def get_initial_lots(self) -> float:
        """Calculate initial entry lot size based on first tranche allocation.

        Returns:
            Initial entry volume in lots rounded to 2 decimal places.
        """
        first_share = self.tranche_shares[0]
        calculated = self.total_planned_lots * first_share
        return max(round(calculated, 2), 0.01)

    def check_scale_in(
        self,
        position: Any,
        candle: Any,
    ) -> Optional[ScaleInSignal]:
        """Check if favorable excursion warrants adding the next tranche.

        Parameters:
            position: Active Position object with direction, entry_price, tranches_filled.
            candle: Current Candle object with high and low prices.

        Returns:
            ScaleInSignal if addition condition met, else None.
        """
        current_tranches = getattr(position, "tranches_filled", 1)
        if current_tranches >= self.max_tranches:
            return None

        d = position.direction
        favorable_excursion = (candle.high - position.entry_price) if d == 1 else (position.entry_price - candle.low)

        if self.model == PyramidModel.EQUAL_SPLIT or self.model == PyramidModel.FRONT_LOADED:
            if current_tranches == 1 and favorable_excursion >= 15.0:
                next_share = self.tranche_shares[1]
                add_lots = max(round(self.total_planned_lots * next_share, 2), 0.01)
                fill_p = position.entry_price + (15.0 * d)
                return ScaleInSignal(
                    tranche_index=2,
                    additional_lots=add_lots,
                    fill_price=fill_p,
                    move_to_be=True,
                    new_sl=position.entry_price,
                )
            if current_tranches == 2 and favorable_excursion >= 30.0:
                next_share = self.tranche_shares[2]
                add_lots = max(round(self.total_planned_lots * next_share, 2), 0.01)
                fill_p = position.entry_price + (30.0 * d)
                return ScaleInSignal(
                    tranche_index=3,
                    additional_lots=add_lots,
                    fill_price=fill_p,
                    move_to_be=False,
                )

        if self.model == PyramidModel.INVERSE_PYRAMID:
            if current_tranches == 1 and favorable_excursion >= 20.0:
                next_share = self.tranche_shares[1]
                add_lots = max(round(self.total_planned_lots * next_share, 2), 0.01)
                fill_p = position.entry_price + (20.0 * d)
                return ScaleInSignal(
                    tranche_index=2,
                    additional_lots=add_lots,
                    fill_price=fill_p,
                    move_to_be=True,
                    new_sl=position.entry_price,
                )
            if current_tranches == 2 and favorable_excursion >= 40.0:
                next_share = self.tranche_shares[2]
                add_lots = max(round(self.total_planned_lots * next_share, 2), 0.01)
                fill_p = position.entry_price + (40.0 * d)
                return ScaleInSignal(
                    tranche_index=3,
                    additional_lots=add_lots,
                    fill_price=fill_p,
                    move_to_be=False,
                )

        if self.model == PyramidModel.MOMENTUM_CONFIRMED:
            if current_tranches == 1 and favorable_excursion >= 15.0:
                next_share = self.tranche_shares[1]
                add_lots = max(round(self.total_planned_lots * next_share, 2), 0.01)
                fill_p = position.entry_price + (15.0 * d)
                return ScaleInSignal(
                    tranche_index=2,
                    additional_lots=add_lots,
                    fill_price=fill_p,
                    move_to_be=True,
                    new_sl=position.entry_price,
                )

        if self.model == PyramidModel.ADAPTIVE_TRANCHE:
            triggers = [10.0, 20.0, 30.0]
            target_idx = current_tranches
            if target_idx <= len(triggers):
                required_excursion = triggers[target_idx - 1]
                if favorable_excursion >= required_excursion:
                    next_share = self.tranche_shares[target_idx]
                    add_lots = max(round(self.total_planned_lots * next_share, 2), 0.01)
                    fill_p = position.entry_price + (required_excursion * d)
                    trail_sl = fill_p - (10.0 * d)
                    return ScaleInSignal(
                        tranche_index=target_idx + 1,
                        additional_lots=add_lots,
                        fill_price=fill_p,
                        move_to_be=True,
                        new_sl=trail_sl,
                    )

        return None

    def check_scale_out(
        self,
        position: Any,
        candle: Any,
    ) -> Optional[ScaleOutSignal]:
        """Check if position should execute a partial-close derisking scalp.

        Parameters:
            position: Active Position object.
            candle: Current Candle object.

        Returns:
            ScaleOutSignal if partial close condition met, else None.
        """
        if self.model != PyramidModel.RISK_FREE_RUNNER:
            return None

        partial_closes = getattr(position, "partial_closes", [])
        if len(partial_closes) > 0:
            return None

        d = position.direction
        favorable_excursion = (candle.high - position.entry_price) if d == 1 else (position.entry_price - candle.low)

        if favorable_excursion >= 15.0:
            lots_to_close = max(round(position.lots * 0.50, 2), 0.01)
            exit_p = position.entry_price + (15.0 * d)
            new_sl = position.entry_price + (1.0 * d)
            return ScaleOutSignal(
                fraction_to_close=0.50,
                lots_to_close=lots_to_close,
                exit_price=exit_p,
                move_to_be=True,
                new_sl=new_sl,
            )

        return None
