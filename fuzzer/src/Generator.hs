module Generator
  ( genProfile
  , genIncompatibleProfile
  , genAdversarialProfile
  , genValidProfile
  ) where

import Test.QuickCheck
import Types

instance Arbitrary EngineType where
  arbitrary = elements [minBound .. maxBound]

instance Arbitrary RiskModel where
  arbitrary = elements [minBound .. maxBound]

instance Arbitrary EntryMode where
  arbitrary = elements [minBound .. maxBound]

instance Arbitrary PyramidModel where
  arbitrary = elements [minBound .. maxBound]

instance Arbitrary ExitModel where
  arbitrary = elements [minBound .. maxBound]

instance Arbitrary MarketFilter where
  arbitrary = elements [minBound .. maxBound]

instance Arbitrary ProfileParameters where
  arbitrary = do
    sl <- choose (10.0, 150.0)
    tp <- choose (10.0, 300.0)
    buf <- choose (0.0, 20.0)
    tt <- choose (0.0, 50.0)
    td <- choose (0.0, 50.0)
    sp <- choose (0.5, 10.0)
    tr <- choose (1, 4)
    cd <- choose (10.0, 600.0)
    mbl <- frequency [(3, pure Nothing), (7, Just <$> choose (0.1, 50.0))]
    pure ProfileParameters
      { slPts = sl
      , tpPts = tp
      , bufferPts = buf
      , trailTriggerPts = tt
      , trailDistPts = td
      , maxSpreadPts = sp
      , maxTranches = tr
      , cooldownSeconds = cd
      , baseLotSize = mbl
      }

instance Arbitrary RiskBounds where
  arbitrary = do
    mr <- choose (0.001, 0.030)
    mdl <- choose (0.01, 0.10)
    af <- choose (85000.0, 95000.0)
    ml <- choose (0.1, 100.0)
    pure RiskBounds
      { maxRiskPct = mr
      , maxDailyLossPct = mdl
      , accountFloor = af
      , maxLotSize = ml
      }

instance Arbitrary Profile where
  arbitrary = frequency
    [ (5, genProfile)
    , (4, genValidProfile)
    , (1, genAdversarialProfile)
    ]

genProfile :: Gen Profile
genProfile = do
  eng <- arbitrary
  inst <- elements ["US100.cash", "BTCUSD", "EURUSD", "XAUUSD"]
  rm <- arbitrary
  em <- arbitrary
  pm <- arbitrary
  xm <- arbitrary
  flts <- sublistOf [minBound .. maxBound]
  params <- arbitrary
  bounds <- arbitrary
  pure Profile
    { profileId = "fuzz_profile"
    , engine = eng
    , instrument = inst
    , version = "1.0.0"
    , riskModel = rm
    , entryMode = em
    , pyramidModel = pm
    , exitModel = xm
    , filters = flts
    , parameters = params
    , riskBounds = bounds
    }

genValidProfile :: Gen Profile
genValidProfile = do
  eng <- elements [LondonReversal, OmniBreakout]
  inst <- elements ["US100.cash", "EURUSD", "XAUUSD"]
  rm <- elements [ConservativeRamp, FixedLow, VolatilityScaled]
  em <- case eng of
    LondonReversal -> elements [SweepConfirmation, DynamicBuffer, TimeWeighted, OrderFlowSpreadGate]
    OmniBreakout -> elements [CloseConfirmation, StopOrderAtRange, VolumeSpikeGate, RetestEntry]
  pm <- elements [NoPyramid, EqualSplit, FrontLoaded, RiskFreeRunner]
  xm <- case pm of
    NoPyramid -> elements [FixedSlTp, FixedSlTrail, AtrDynamicTrail, BreakevenRunner]
    _ -> elements [FixedSlTrail, AtrDynamicTrail, BreakevenRunner]
  flts <- elements
    [ [AtrGate, SpreadGate]
    , [AtrGate, DayOfWeek]
    , [SpreadGate, DayOfWeek]
    ]
  sl <- choose (30.0, 60.0)
  tp <- choose (20.0, 80.0)
  sp <- choose (1.0, 3.0)
  tr <- choose (1, 2)
  pure Profile
    { profileId = "valid_fuzz_profile"
    , engine = eng
    , instrument = inst
    , version = "1.0.0"
    , riskModel = rm
    , entryMode = em
    , pyramidModel = pm
    , exitModel = xm
    , filters = flts
    , parameters = ProfileParameters
        { slPts = sl
        , tpPts = tp
        , bufferPts = 0.0
        , trailTriggerPts = 15.0
        , trailDistPts = 15.0
        , maxSpreadPts = sp
        , maxTranches = tr
        , cooldownSeconds = 60.0
        , baseLotSize = Just 3.0
        }
    , riskBounds = RiskBounds
        { maxRiskPct = 0.0075
        , maxDailyLossPct = 0.045
        , accountFloor = 90000.0
        , maxLotSize = 15.0
        }
    }

genIncompatibleProfile :: Gen Profile
genIncompatibleProfile = do
  base <- genProfile
  incId <- chooseInt (1, 7)
  case incId of
    1 -> do
      let eng = LondonReversal
      em <- elements [StopOrderAtRange, CloseConfirmation, VolumeSpikeGate, RetestEntry]
      pure base { engine = eng, entryMode = em }
    2 -> do
      pm <- elements [EqualSplit, FrontLoaded, InversePyramid, AdaptiveTranche]
      pure base { pyramidModel = pm, exitModel = FixedSlTp }
    3 -> do
      rm <- elements [AggressiveFlat, AntiMartingale]
      pm <- elements [InversePyramid, AdaptiveTranche]
      pure base { riskModel = rm, pyramidModel = pm }
    4 -> do
      pm <- elements [AdaptiveTranche, MomentumConfirmed]
      pure base { pyramidModel = pm, exitModel = TimeBased }
    5 -> pure base { entryMode = BlindLimit, filters = [] }
    6 -> do
      sl <- choose (1.0, 19.0)
      pure base { exitModel = Chandelier, parameters = (parameters base) { slPts = sl } }
    _ -> do
      lot <- choose (0.51, 10.0)
      pure base
        { instrument = "BTCUSD"
        , parameters = (parameters base) { baseLotSize = Just lot }
        , riskBounds = (riskBounds base) { maxLotSize = lot }
        }

genAdversarialProfile :: Gen Profile
genAdversarialProfile = do
  base <- genProfile
  advType <- chooseInt (1, 4)
  case advType of
    1 -> do
      hugeLots <- choose (30.0, 100.0)
      pure base
        { parameters = (parameters base) { slPts = 100.0, baseLotSize = Just hugeLots, maxTranches = 4 }
        , riskBounds = (riskBounds base) { maxLotSize = hugeLots, maxRiskPct = 0.05 }
        }
    2 -> do
      pure base
        { instrument = "BTCUSD"
        , parameters = (parameters base) { baseLotSize = Just 2.0 }
        , riskBounds = (riskBounds base) { maxLotSize = 2.0 }
        }
    3 -> do
      pure base
        { riskBounds = (riskBounds base) { maxDailyLossPct = 0.08 }
        }
    _ -> genIncompatibleProfile
