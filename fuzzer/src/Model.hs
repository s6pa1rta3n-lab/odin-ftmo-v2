module Model
  ( checkIncompatibilities
  , computeLotSize
  , verifyProfile
  , maxCompositeRiskDollars
  ) where

import Types

checkIncompatibilities :: Profile -> [String]
checkIncompatibilities p = concat
  [ [ "INC-01: Cross-engine entry mode mismatch"
    | (engine p == LondonReversal && not (isLondonEntry (entryMode p)))
   || (engine p == OmniBreakout && not (isOmniEntry (entryMode p)))
    ]
  , [ "INC-02: Scale-in pyramiding model incompatible with static fixed_sl_tp"
    | isScaleInPyramid (pyramidModel p) && exitModel p == FixedSlTp
    ]
  , [ "INC-03: High-exposure risk model combined with backloaded pyramiding"
    | isHighRiskModel (riskModel p) && isBackloadedPyramid (pyramidModel p)
    ]
  , [ "INC-04: Multi-tranche scale-in model incompatible with time_based exit"
    | isComplexScaleIn (pyramidModel p) && exitModel p == TimeBased
    ]
  , [ "INC-05: Blind limit entry requires at least one market context filter"
    | entryMode p == BlindLimit && null (filters p)
    ]
  , [ "INC-06: Chandelier wide stop exit incompatible with tight SL or aggressive risk"
    | exitModel p == Chandelier
   && (slPts (parameters p) < 20.0
       || riskModel p == AggressiveFlat
       || maxRiskPct (riskBounds p) > 0.010)
    ]
  , [ "INC-07: Crypto instruments require position size <= 0.50 lots"
    | (instrument p == "BTCUSD" || instrument p == "ETHUSD")
   && (maxLotSize (riskBounds p) > maxCryptoPositionLots
       || maybe False (> maxCryptoPositionLots) (baseLotSize (parameters p)))
    ]
  ]

maxCompositeRiskDollars :: Double -> Double
maxCompositeRiskDollars eq =
  let pctLimit = 0.015 * eq
      marginLimit = max 0.0 (0.25 * (eq - absoluteTotalLossFloor))
  in min pctLimit marginLimit

computeLotSize :: Profile -> InstrumentSpec -> Double -> Double
computeLotSize p spec eq =
  let baseRiskPct = case riskModel p of
        ConservativeRamp
          | eq < 98000.0 -> 0.0025
          | eq < 102000.0 -> 0.0050
          | otherwise -> 0.0075
        FixedLow -> 0.0035
        AggressiveFlat -> 0.0075
        KellyCriterion -> 0.0075
        AntiMartingale -> 0.0075
        VolatilityScaled -> 0.0060
        EquityCurve -> 0.0050
      effRiskPct = min baseRiskPct (maxRiskPct (riskBounds p))
      riskDollars = eq * effRiskPct
      sl = slPts (parameters p)
  in if sl <= 0.0 then 0.0 else
       let rawLots = riskDollars / (sl * specTickValue spec)
           withBase = case baseLotSize (parameters p) of
             Just bl -> max bl rawLots
             Nothing -> rawLots
           capped = min withBase (maxLotSize (riskBounds p))
           rounded = fromIntegral (round (capped * 100.0) :: Int) / 100.0
       in max 0.01 rounded

verifyProfile :: Profile -> VerificationResult
verifyProfile p =
  let spec = getInstrumentSpec (instrument p)
      incompatViolations = checkIncompatibilities p
      initialLots = computeLotSize p spec currentAccountEquity
      trancheMultiplier = if pyramidModel p == NoPyramid then 1 else max 1 (maxTranches (parameters p))
      totalLots = initialLots * fromIntegral trancheMultiplier
      sl = slPts (parameters p)
      compositeRisk = (totalLots * sl * specTickValue spec) + (totalLots * specCommission spec)
      maxCompositeBudget = maxCompositeRiskDollars currentAccountEquity
      inv3Passed = compositeRisk <= maxCompositeBudget
                && (compositeRisk / currentAccountEquity) <= maxCompositeRiskCeilingPct

      shockEffectiveSl = sl + (1.5 * specAtr spec) + (3.0 * specSpread spec)
      shockLoss = (totalLots * shockEffectiveSl * specTickValue spec) + (totalLots * specCommission spec)
      circuitBreakerLimit = circuitBreakerDailyLossPct * currentAccountEquity
      inv4Passed = shockLoss <= circuitBreakerLimit

      marginReq = (totalLots * specContractSize spec * specPrice spec) / specLeverage spec
      maxMargin = maxFreeMarginConsumptionPct * currentAccountEquity
      cryptoOk = specAssetClass spec /= Crypto || totalLots <= maxCryptoPositionLots
      inv5Passed = marginReq <= maxMargin && cryptoOk

      singleTradeLoss = (initialLots * sl * specTickValue spec) + (initialLots * specCommission spec)
      inv2Passed = singleTradeLoss <= circuitBreakerLimit
                && maxDailyLossPct (riskBounds p) <= circuitBreakerDailyLossPct

      simulateFloor :: Double -> Double -> Double -> Int -> (Bool, Double)
      simulateFloor eq wm dailyLoss step
        | step > 10 = (eq >= absoluteTotalLossFloor, eq)
        | eq <= emergencyLiquidationFloor = (eq >= absoluteTotalLossFloor, eq)
        | otherwise =
            let lots = computeLotSize p spec eq
                loss = (lots * sl * specTickValue spec) + (lots * specCommission spec)
                maxDaily = circuitBreakerDailyLossPct * wm
            in if dailyLoss + loss >= maxDaily
               then let lossApplied = min loss (maxDaily - dailyLoss)
                        nextEq = eq - lossApplied
                    in if nextEq < absoluteTotalLossFloor
                       then (False, nextEq)
                       else simulateFloor nextEq nextEq 0.0 (step + 1)
               else let nextEq = eq - loss
                    in if nextEq < absoluteTotalLossFloor
                       then (False, nextEq)
                       else simulateFloor nextEq wm (dailyLoss + loss) (step + 1)

      (inv1Passed, worstEq) = simulateFloor currentAccountEquity currentAccountEquity 0.0 1
      compPassed = null incompatViolations
      allPassed = inv1Passed && inv2Passed && inv3Passed && inv4Passed && inv5Passed && compPassed

      violations = concat
        [ incompatViolations
        , [ "Invariant 1: Floor breach" | not inv1Passed ]
        , [ "Invariant 2: Daily loss breach" | not inv2Passed ]
        , [ "Invariant 3: Composite risk breach" | not inv3Passed ]
        , [ "Invariant 4: Adverse gap breach" | not inv4Passed ]
        , [ "Invariant 5: Margin or leverage breach" | not inv5Passed ]
        ]
  in VerificationResult
       { resVerified = allPassed
       , resFloorPreserved = inv1Passed
       , resDailyLossBounded = inv2Passed
       , resCompositeRiskValid = inv3Passed
       , resGapResilient = inv4Passed
       , resMarginFeasible = inv5Passed
       , resCompatibilityPassed = compPassed
       , resWorstCaseEquity = worstEq
       , resViolations = violations
       }
