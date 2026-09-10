module Main (main) where

import System.Exit (exitFailure, exitSuccess)
import Test.QuickCheck
import Properties

main :: IO ()
main = do
  putStrLn "Starting Haskell QuickCheck Fuzzer (10,000 runs per property)..."
  let qcArgs = stdArgs { maxSuccess = 10000 }

  putStrLn "[1/6] Testing Invariant 1: Floor Preservation (prop_ftmo_floor_preserved)..."
  r1 <- quickCheckWithResult qcArgs prop_ftmo_floor_preserved

  putStrLn "[2/6] Testing Invariant 2: Daily Loss Bound (prop_daily_loss_bounded)..."
  r2 <- quickCheckWithResult qcArgs prop_daily_loss_bounded

  putStrLn "[3/6] Testing Incompatibility Matrix (prop_incompatibilities_rejected)..."
  r3 <- quickCheckWithResult qcArgs prop_incompatibilities_rejected

  putStrLn "[4/6] Testing Invariant 5: Margin & Leverage (prop_margin_leverage_feasible)..."
  r4 <- quickCheckWithResult qcArgs prop_margin_leverage_feasible

  putStrLn "[5/6] Testing Lot Sizing Monotonicity (prop_lot_monotonicity)..."
  r5 <- quickCheckWithResult qcArgs prop_lot_monotonicity

  putStrLn "[6/6] Testing Circuit Breaker Buffer (prop_circuit_breaker_buffer)..."
  r6 <- quickCheckWithResult qcArgs prop_circuit_breaker_buffer

  let allPassed = all isSuccess [r1, r2, r3, r4, r5, r6]
  if allPassed
    then do
      putStrLn "SUCCESS: All 6 properties passed 10,000 QuickCheck runs with zero violations!"
      exitSuccess
    else do
      putStrLn "FAILURE: One or more QuickCheck properties reported violations!"
      exitFailure
