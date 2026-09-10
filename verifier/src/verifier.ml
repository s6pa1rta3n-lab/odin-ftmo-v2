let () =
  if Array.length Sys.argv < 2 then begin
    Printf.eprintf "Usage: %s <profile_path.json>\n" Sys.argv.(0);
    exit 2
  end;

  let profile_path = Sys.argv.(1) in
  if not (Sys.file_exists profile_path) then begin
    let err_json =
      Json.JAssoc
        [
          ("verified", Json.JBool false);
          ("error", Json.JString ("File not found: " ^ profile_path));
        ]
    in
    print_endline (Json.to_pretty_string err_json);
    exit 1
  end;

  let raw_json =
    try Json.from_file profile_path
    with exn ->
      let err_json =
        Json.JAssoc
          [
            ("verified", Json.JBool false);
            ("error", Json.JString ("JSON parse error: " ^ Printexc.to_string exn));
          ]
      in
      print_endline (Json.to_pretty_string err_json);
      exit 1
  in

  match Model_checker.parse_profile raw_json with
  | Error err_msg ->
      let err_json =
        Json.JAssoc
          [
            ("verified", Json.JBool false);
            ("error", Json.JString ("Profile validation error: " ^ err_msg));
          ]
      in
      print_endline (Json.to_pretty_string err_json);
      exit 1
  | Ok profile ->
      let report = Model_checker.verify_profile profile in
      let output_json = Model_checker.json_of_report report in
      print_endline (Json.to_pretty_string output_json);
      if report.verified then exit 0 else exit 1
