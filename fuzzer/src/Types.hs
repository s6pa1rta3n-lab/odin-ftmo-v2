module Types
  ( EngineType(..)
  , RiskModel(..)
  , EntryMode(..)
  , PyramidModel(..)
  , ExitModel(..)
  , MarketFilter(..)
  , ProfileParameters(..)
  , RiskBounds(..)
  , Profile(..)
  , AssetClass(..)
  , InstrumentSpec(..)
  , VerificationResult(..)
  , isLondonEntry
  , isOmniEntry
  , isScaleInPyramid
  , isHighRiskModel
  , isBackloadedPyramid
  , isComplexScaleIn
  , getInstrumentSpec
  , initialAccountBalance
  , currentAccountEquity
  , absoluteTotalLossFloor
  , emergencyLiquidationFloor
  , circuitBreakerDailyLossPct
  , maxCompositeRiskCeilingPct
  , maxFreeMarginConsumptionPct
  , maxCryptoPositionLots
  ) where

data EngineType
  = LondonReversal
  | OmniBreakout
  deriving (Eq, Show, Enum, Bounded)

data RiskModel
  = ConservativeRamp
  | FixedLow
  | AggressiveFlat
  | KellyCriterion
  | AntiMartingale
  | VolatilityScaled
  | EquityCurve
  deriving (Eq, Show, Enum, Bounded)

data EntryMode
  = BlindLimit
  | SweepConfirmation
  | DynamicBuffer
  | TimeWeighted
  | OrderFlowSpreadGate
  | MultiTimeframe
  | HybridSweepTimeSpread
  | StopOrderAtRange
  | CloseConfirmation
  | VolumeSpikeGate
  | RetestEntry
  | MomentumThreshold
  | DualTimeframe
  | HybridRetestVolumeSpread
  deriving (Eq, Show, Enum, Bounded)

data PyramidModel
  = NoPyramid
  | EqualSplit
  | FrontLoaded
  | InversePyramid
  | MomentumConfirmed
  | RiskFreeRunner
  | AdaptiveTranche
  deriving (Eq, Show, Enum, Bounded)

data ExitModel
  = FixedSlTp
  | FixedSlTrail
  | AtrDynamicTrail
  | BreakevenRunner
  | TimeBased
  | Chandelier
  | MultiTargetCascade
  deriving (Eq, Show, Enum, Bounded)

data MarketFilter
  = AtrGate
  | VixRegime
  | SpreadGate
  | NewsBlackout
  | PreSessionMomentum
  | VolatilityPercentile
  | DayOfWeek
  | OrbWidthGate
  | PreOpenTrend
  | LondonSessionResult
  deriving (Eq, Show, Enum, Bounded, Ord)

data ProfileParameters = ProfileParameters
  { slPts :: !Double
  , tpPts :: !Double
  , bufferPts :: !Double
  , trailTriggerPts :: !Double
  , trailDistPts :: !Double
  , maxSpreadPts :: !Double
  , maxTranches :: !Int
  , cooldownSeconds :: !Double
  , baseLotSize :: !(Maybe Double)
  } deriving (Eq, Show)

data RiskBounds = RiskBounds
  { maxRiskPct :: !Double
  , maxDailyLossPct :: !Double
  , accountFloor :: !Double
  , maxLotSize :: !Double
  } deriving (Eq, Show)

data Profile = Profile
  { profileId :: !String
  , engine :: !EngineType
  , instrument :: !String
  , version :: !String
  , riskModel :: !RiskModel
  , entryMode :: !EntryMode
  , pyramidModel :: !PyramidModel
  , exitModel :: !ExitModel
  , filters :: ![MarketFilter]
  , parameters :: !ProfileParameters
  , riskBounds :: !RiskBounds
  } deriving (Eq, Show)

data AssetClass = Index | Forex | Commodity | Crypto
  deriving (Eq, Show)

data InstrumentSpec = InstrumentSpec
  { specSymbol :: !String
  , specAssetClass :: !AssetClass
  , specLeverage :: !Double
  , specContractSize :: !Double
  , specTickValue :: !Double
  , specCommission :: !Double
  , specSpread :: !Double
  , specPrice :: !Double
  , specAtr :: !Double
  } deriving (Eq, Show)

data VerificationResult = VerificationResult
  { resVerified :: !Bool
  , resFloorPreserved :: !Bool
  , resDailyLossBounded :: !Bool
  , resCompositeRiskValid :: !Bool
  , resGapResilient :: !Bool
  , resMarginFeasible :: !Bool
  , resCompatibilityPassed :: !Bool
  , resWorstCaseEquity :: !Double
  , resViolations :: ![String]
  } deriving (Eq, Show)

isLondonEntry :: EntryMode -> Bool
isLondonEntry m = m `elem`
  [ BlindLimit
  , SweepConfirmation
  , DynamicBuffer
  , TimeWeighted
  , OrderFlowSpreadGate
  , MultiTimeframe
  , HybridSweepTimeSpread
  ]

isOmniEntry :: EntryMode -> Bool
isOmniEntry m = m `elem`
  [ StopOrderAtRange
  , CloseConfirmation
  , VolumeSpikeGate
  , RetestEntry
  , MomentumThreshold
  , DualTimeframe
  , HybridRetestVolumeSpread
  ]

isScaleInPyramid :: PyramidModel -> Bool
isScaleInPyramid m = m `elem`
  [ EqualSplit
  , FrontLoaded
  , InversePyramid
  , AdaptiveTranche
  , MomentumConfirmed
  ]

isHighRiskModel :: RiskModel -> Bool
isHighRiskModel m = m `elem` [AggressiveFlat, AntiMartingale]

isBackloadedPyramid :: PyramidModel -> Bool
isBackloadedPyramid m = m `elem` [InversePyramid, AdaptiveTranche]

isComplexScaleIn :: PyramidModel -> Bool
isComplexScaleIn m = m `elem` [AdaptiveTranche, MomentumConfirmed]

initialAccountBalance :: Double
initialAccountBalance = 100000.0

currentAccountEquity :: Double
currentAccountEquity = 94939.28

absoluteTotalLossFloor :: Double
absoluteTotalLossFloor = 90000.0

emergencyLiquidationFloor :: Double
emergencyLiquidationFloor = 90500.0

circuitBreakerDailyLossPct :: Double
circuitBreakerDailyLossPct = 0.045

maxCompositeRiskCeilingPct :: Double
maxCompositeRiskCeilingPct = 0.0130

maxFreeMarginConsumptionPct :: Double
maxFreeMarginConsumptionPct = 0.50

maxCryptoPositionLots :: Double
maxCryptoPositionLots = 0.50

getInstrumentSpec :: String -> InstrumentSpec
getInstrumentSpec "BTCUSD" = InstrumentSpec "BTCUSD" Crypto 1.0 1.0 1.0 0.0 15.0 60000.0 800.0
getInstrumentSpec "ETHUSD" = InstrumentSpec "ETHUSD" Crypto 1.0 1.0 1.0 0.0 1.0 2500.0 45.0
getInstrumentSpec "EURUSD" = InstrumentSpec "EURUSD" Forex 100.0 100000.0 10.0 3.0 0.2 1.09 0.0050
getInstrumentSpec "GBPUSD" = InstrumentSpec "GBPUSD" Forex 100.0 100000.0 10.0 3.0 0.5 1.31 0.0060
getInstrumentSpec "XAUUSD" = InstrumentSpec "XAUUSD" Commodity 30.0 100.0 1.0 3.0 2.5 2500.0 15.0
getInstrumentSpec _ = InstrumentSpec "US100.cash" Index 50.0 1.0 1.0 0.0 1.0 19500.0 40.0
