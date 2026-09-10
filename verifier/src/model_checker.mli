(** Model checking and formal verification algorithms for FTMO profiles. *)

(** Parses a profile AST from a JSON object. *)
val parse_profile : Json.json -> (Types.profile, string) result

(** Evaluates the 7-class module incompatibility matrix (INC-01 through INC-07). Returns a list of violation messages. *)
val check_incompatibilities : Types.profile -> string list

(** Computes position sizing in lots for a profile at a given equity level. *)
val compute_lot_size : Types.profile -> Ftmo_specs.instrument_spec -> float -> float

(** Executes the full formal verification pipeline across Invariants 1-5 and incompatibility checks. *)
val verify_profile : Types.profile -> Types.verification_report

(** Serializes a verification report into a JSON AST. *)
val json_of_report : Types.verification_report -> Json.json
