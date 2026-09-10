(** Zero-dependency pure OCaml JSON parser and serializer. *)

type json =
  | JNull
  | JBool of bool
  | JInt of int
  | JFloat of float
  | JString of string
  | JList of json list
  | JAssoc of (string * json) list

(** Parses a JSON formatted string into a json AST. Raises Failure on syntax error. *)
val from_string : string -> json

(** Reads a file from disk and parses its JSON content. Raises Failure or Sys_error on failure. *)
val from_file : string -> json

(** Serializes a json AST into a compact string representation. *)
val to_string : json -> string

(** Serializes a json AST into a formatted multi-line string. *)
val to_pretty_string : ?indent:int -> json -> string

(** Extracts an optional field by key from a JAssoc object. *)
val get_field : string -> json -> json option

(** Extracts an optional string value for a given field from a JAssoc object. *)
val get_string : string -> json -> string option

(** Extracts an optional float value (or converted int) for a given field from a JAssoc object. *)
val get_float : string -> json -> float option

(** Extracts an optional integer value for a given field from a JAssoc object. *)
val get_int : string -> json -> int option

(** Extracts an optional boolean value for a given field from a JAssoc object. *)
val get_bool : string -> json -> bool option

(** Extracts an optional list of JSON values for a given field from a JAssoc object. *)
val get_list : string -> json -> json list option

(** Extracts an optional key-value association list from a JAssoc object. *)
val get_assoc : string -> json -> (string * json) list option
