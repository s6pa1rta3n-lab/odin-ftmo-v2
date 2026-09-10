type json =
  | JNull
  | JBool of bool
  | JInt of int
  | JFloat of float
  | JString of string
  | JList of json list
  | JAssoc of (string * json) list

type token =
  | TokLBrace
  | TokRBrace
  | TokLBracket
  | TokRBracket
  | TokColon
  | TokComma
  | TokNull
  | TokTrue
  | TokFalse
  | TokString of string
  | TokNumber of string
  | TokEOF

let tokenize s =
  let len = String.length s in
  let pos = ref 0 in
  let tokens = ref [] in

  let is_whitespace = function
    | ' ' | '\t' | '\r' | '\n' -> true
    | _ -> false
  in

  let is_number_char = function
    | '0' .. '9' | '-' | '+' | '.' | 'e' | 'E' -> true
    | _ -> false
  in

  while !pos < len do
    let c = s.[!pos] in
    if is_whitespace c then
      incr pos
    else
      match c with
      | '{' ->
          tokens := TokLBrace :: !tokens;
          incr pos
      | '}' ->
          tokens := TokRBrace :: !tokens;
          incr pos
      | '[' ->
          tokens := TokLBracket :: !tokens;
          incr pos
      | ']' ->
          tokens := TokRBracket :: !tokens;
          incr pos
      | ':' ->
          tokens := TokColon :: !tokens;
          incr pos
      | ',' ->
          tokens := TokComma :: !tokens;
          incr pos
      | '"' ->
          incr pos;
          let buf = Buffer.create 32 in
          let closed = ref false in
          while !pos < len && not !closed do
            let sc = s.[!pos] in
            if sc = '\\' then begin
              incr pos;
              if !pos >= len then failwith "Unterminated escape sequence in JSON string";
              let esc = s.[!pos] in
              let mapped =
                match esc with
                | '"' -> '"'
                | '\\' -> '\\'
                | '/' -> '/'
                | 'b' -> '\b'
                | 'f' -> '\012'
                | 'n' -> '\n'
                | 'r' -> '\r'
                | 't' -> '\t'
                | _ -> esc
              in
              Buffer.add_char buf mapped;
              incr pos
            end else if sc = '"' then begin
              closed := true;
              incr pos
            end else begin
              Buffer.add_char buf sc;
              incr pos
            end
          done;
          if not !closed then failwith "Unterminated JSON string";
          tokens := TokString (Buffer.contents buf) :: !tokens
      | '-' | '0' .. '9' ->
          let start_p = !pos in
          while !pos < len && is_number_char s.[!pos] do
            incr pos
          done;
          let num_str = String.sub s start_p (!pos - start_p) in
          tokens := TokNumber num_str :: !tokens
      | 't' when !pos + 3 < len && String.sub s !pos 4 = "true" ->
          pos := !pos + 4;
          tokens := TokTrue :: !tokens
      | 'f' when !pos + 4 < len && String.sub s !pos 5 = "false" ->
          pos := !pos + 5;
          tokens := TokFalse :: !tokens
      | 'n' when !pos + 3 < len && String.sub s !pos 4 = "null" ->
          pos := !pos + 4;
          tokens := TokNull :: !tokens
      | other ->
          failwith (Printf.sprintf "Unexpected character in JSON: %c at position %d" other !pos)
  done;
  List.rev (TokEOF :: !tokens)

let parse_number num_str =
  if String.contains num_str '.' || String.contains num_str 'e' || String.contains num_str 'E' then
    match Float.of_string_opt num_str with
    | Some f -> JFloat f
    | None -> failwith (Printf.sprintf "Invalid float in JSON: %s" num_str)
  else
    match int_of_string_opt num_str with
    | Some i -> JInt i
    | None ->
        match Float.of_string_opt num_str with
        | Some f -> JFloat f
        | None -> failwith (Printf.sprintf "Invalid integer in JSON: %s" num_str)

let parse_tokens token_list =
  let stream = ref token_list in

  let peek () =
    match !stream with
    | [] -> TokEOF
    | hd :: _ -> hd
  in

  let consume () =
    match !stream with
    | [] -> TokEOF
    | hd :: tl ->
        stream := tl;
        hd
  in

  let expect expected =
    let actual = consume () in
    if actual <> expected then
      failwith "Unexpected token in JSON parse stream"
  in

  let rec parse_value () =
    match peek () with
    | TokLBrace -> parse_object ()
    | TokLBracket -> parse_array ()
    | TokString s ->
        ignore (consume ());
        JString s
    | TokNumber n ->
        ignore (consume ());
        parse_number n
    | TokTrue ->
        ignore (consume ());
        JBool true
    | TokFalse ->
        ignore (consume ());
        JBool false
    | TokNull ->
        ignore (consume ());
        JNull
    | _ -> failwith "Malformed JSON value"

  and parse_object () =
    expect TokLBrace;
    if peek () = TokRBrace then begin
      ignore (consume ());
      JAssoc []
    end else
      let rec parse_members acc =
        let key =
          match consume () with
          | TokString s -> s
          | _ -> failwith "Expected string object key"
        in
        expect TokColon;
        let v = parse_value () in
        let next_acc = (key, v) :: acc in
        match peek () with
        | TokComma ->
            ignore (consume ());
            parse_members next_acc
        | TokRBrace ->
            ignore (consume ());
            JAssoc (List.rev next_acc)
        | _ -> failwith "Expected ',' or '}' in object"
      in
      parse_members []

  and parse_array () =
    expect TokLBracket;
    if peek () = TokRBracket then begin
      ignore (consume ());
      JList []
    end else
      let rec parse_elements acc =
        let elem = parse_value () in
        let next_acc = elem :: acc in
        match peek () with
        | TokComma ->
            ignore (consume ());
            parse_elements next_acc
        | TokRBracket ->
            ignore (consume ());
            JList (List.rev next_acc)
        | _ -> failwith "Expected ',' or ']' in array"
      in
      parse_elements []
  in

  let root = parse_value () in
  if peek () <> TokEOF then
    failwith "Trailing characters after JSON root"
  else
    root

let from_string s =
  let tokens = tokenize s in
  parse_tokens tokens

let from_file path =
  let ic = open_in path in
  let n = in_channel_length ic in
  let s = really_input_string ic n in
  close_in ic;
  from_string s

let escape_string s =
  let buf = Buffer.create (String.length s + 8) in
  Buffer.add_char buf '"';
  String.iter
    (function
      | '"' -> Buffer.add_string buf "\\\""
      | '\\' -> Buffer.add_string buf "\\\\"
      | '\n' -> Buffer.add_string buf "\\n"
      | '\r' -> Buffer.add_string buf "\\r"
      | '\t' -> Buffer.add_string buf "\\t"
      | c -> Buffer.add_char buf c)
    s;
  Buffer.add_char buf '"';
  Buffer.contents buf

let rec to_string = function
  | JNull -> "null"
  | JBool b -> if b then "true" else "false"
  | JInt i -> string_of_int i
  | JFloat f ->
      let s = Printf.sprintf "%.8f" f in
      let len = String.length s in
      let rec trim_zeros idx =
        if idx > 0 && s.[idx] = '0' && s.[idx - 1] <> '.' then
          trim_zeros (idx - 1)
        else
          idx
      in
      let end_idx = trim_zeros (len - 1) in
      String.sub s 0 (end_idx + 1)
  | JString s -> escape_string s
  | JList l ->
      let items = List.map to_string l in
      "[" ^ String.concat "," items ^ "]"
  | JAssoc kvs ->
      let items =
        List.map
          (fun (k, v) -> escape_string k ^ ":" ^ to_string v)
          kvs
      in
      "{" ^ String.concat "," items ^ "}"

let to_pretty_string ?(indent = 2) json =
  let make_pad level = String.make (level * indent) ' ' in

  let rec format level = function
    | JNull -> "null"
    | JBool b -> if b then "true" else "false"
    | JInt i -> string_of_int i
    | JFloat f ->
        let s = Printf.sprintf "%.8f" f in
        let len = String.length s in
        let rec trim_zeros idx =
          if idx > 0 && s.[idx] = '0' && s.[idx - 1] <> '.' then
            trim_zeros (idx - 1)
          else
            idx
        in
        let end_idx = trim_zeros (len - 1) in
        String.sub s 0 (end_idx + 1)
    | JString s -> escape_string s
    | JList [] -> "[]"
    | JList items ->
        let inner_pad = make_pad (level + 1) in
        let outer_pad = make_pad level in
        let formatted_items =
          List.map (fun x -> inner_pad ^ format (level + 1) x) items
        in
        "[\n" ^ String.concat ",\n" formatted_items ^ "\n" ^ outer_pad ^ "]"
    | JAssoc [] -> "{}"
    | JAssoc kvs ->
        let inner_pad = make_pad (level + 1) in
        let outer_pad = make_pad level in
        let formatted_kvs =
          List.map
            (fun (k, v) ->
              inner_pad ^ escape_string k ^ ": " ^ format (level + 1) v)
            kvs
        in
        "{\n" ^ String.concat ",\n" formatted_kvs ^ "\n" ^ outer_pad ^ "}"
  in
  format 0 json

let get_field key = function
  | JAssoc kvs -> List.assoc_opt key kvs
  | _ -> None

let get_string key json =
  match get_field key json with
  | Some (JString s) -> Some s
  | _ -> None

let get_float key json =
  match get_field key json with
  | Some (JFloat f) -> Some f
  | Some (JInt i) -> Some (float_of_int i)
  | _ -> None

let get_int key json =
  match get_field key json with
  | Some (JInt i) -> Some i
  | _ -> None

let get_bool key json =
  match get_field key json with
  | Some (JBool b) -> Some b
  | _ -> None

let get_list key json =
  match get_field key json with
  | Some (JList l) -> Some l
  | _ -> None

let get_assoc key json =
  match get_field key json with
  | Some (JAssoc kvs) -> Some kvs
  | _ -> None
