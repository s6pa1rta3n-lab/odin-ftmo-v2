module Properties
  ( prop_ftmo_floor_preserved
  , prop_daily_loss_bounded
  , prop_incompatibilities_rejected
  , prop_margin_leverage_feasible
  , prop_lot_monotonicity
  , prop_circuit_breaker_buffer
  ) where

import Test.QuickCheck
import Types
import Model
import Generator

prop_ftmo_floor_preserved :: Profile -> Property
prop_ftmo_floor_preserved p =
  let res = verifyProfile p
  in property (not (resVerified res) || resWorstCaseEquity res >= absoluteTotalLossFloor)

prop_daily_loss_bounded :: Profile -> Property
prop_daily_loss_bounded p =
  let res = verifyProfile p
  in property (not (resVerified res) || resDailyLossBounded res)

prop_incompatibilities_rejected :: Property
prop_incompatibilities_rejected =
  forAll genIncompatibleProfile $ \p ->
    let res = verifyProfile p
    in not (resCompatibilityPassed res) && not (resVerified res)

prop_margin_leverage_feasible :: Profile -> Property
prop_margin_leverage_feasible p =
  let res = verifyProfile p
  in property (not (resVerified res) || resMarginFeasible res)

prop_lot_monotonicity :: Profile -> Property
prop_lot_monotonicity baseProfile =
  forAll (choose (90000.0, 97000.0)) $ \e1 ->
    forAll (choose (e1, 110000.0)) $ \e2 ->
      let p = baseProfile
            { riskModel = ConservativeRamp
            , parameters = (parameters baseProfile) { baseLotSize = Nothing }
            }
          spec = getInstrumentSpec (instrument p)
          l1 = computeLotSize p spec e1
          l2 = computeLotSize p spec e2
      in l1 <= l2 + 1e-4

prop_circuit_breaker_buffer :: Profile -> Property
prop_circuit_breaker_buffer p =
  let res = verifyProfile p
  in property $
       if not (resVerified res)
       then True
       else
         let spec = getInstrumentSpec (instrument p)
             lots = computeLotSize p spec currentAccountEquity
             tranches = if pyramidModel p == NoPyramid then 1 else max 1 (maxTranches (parameters p))
             totalLots = lots * fromIntegral tranches
             cbLoss = circuitBreakerDailyLossPct * currentAccountEquity
             severeSlippageLoss = 5.0 * specSpread spec * totalLots * specTickValue spec
             totalWorstCaseLoss = cbLoss + severeSlippageLoss
             ftmoDailyCeiling = 0.05 * currentAccountEquity
         in totalWorstCaseLoss < ftmoDailyCeiling
