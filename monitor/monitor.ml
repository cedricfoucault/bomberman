open Unix
open Printf

let delay = ref 0.0
let jitter = ref 0.0
let size = ref 0
let fwd_addr = ref ""
let fwd_port = ref 0
let protocol_is_tcp = ref true

(* a heap, for the time being badly implemented with a list + sorting ... *)
module Heap = struct
  type 'a t = {mutable l : 'a list; cmp : 'a -> 'a -> int}
  exception Empty
  let create cmp = {l = []; cmp = cmp}
  let peek h =
    match h.l with
      [] -> raise Empty
      | e :: _ -> e
  let push h e =
    let l = List.merge h.cmp h.l [e] in
      h.l <- l
  let pop h =
    match h.l with
      [] -> raise Empty
      | e :: t -> h.l <- t; e
end

(* makes a delay >= 0ms *)
let make_delay () =
  let d = !delay +. (Random.float (2. *. !jitter)) -. !jitter in
  if d < 0.0 then 0.0 else d

let string_of_sockaddr = function 
  | ADDR_UNIX s -> "unix:" ^ s
  | ADDR_INET (addr,p) -> 
      (string_of_inet_addr addr) ^ ":" ^ (string_of_int p)

let _info_time () =
  let t = Unix.gettimeofday () in
  let tm = Unix.localtime t in
  let t1, _ = Unix.mktime tm in
  let ms = int_of_float ((t -. t1) *. 1000.) in
    Printf.sprintf "%02dh%02d %02d:%03d" tm.tm_hour tm.tm_min tm.tm_sec ms

let info_msg src_addr dst_addr buff len delay =
  let buff2 =
    if len >= 150 then
      (String.sub buff 0 150) ^ "... (trunc)"
    else
      (String.sub buff 0 len)
  in let src = string_of_sockaddr src_addr in
  let dst = string_of_sockaddr dst_addr in
  let ms = int_of_float (delay *. 1000.) in
  Printf.printf "%s from  %-21s to %-22s %2dB delayed %4dms: \"%s\"\n"
      (_info_time ()) src (dst ^ ",") len ms (String.escaped buff2);
  flush_all ()

let info_hello addr =
  Printf.printf "%s HELLO %s\n" (_info_time ()) (string_of_sockaddr addr);
  flush_all ()

let info_bye addr str =
  Printf.printf "%s BYE   %s (reason: %s)\n"
      (_info_time ()) (string_of_sockaddr addr) str;
  flush_all ()

let info_warn s =
  Printf.printf "%s WARN! %s\n" (_info_time ()) s;
  flush_all ()


(*
  TCP functions
*)

module Tcp = struct

  let timenext queue =
    try
      let (_,_,t) = Heap.peek queue in
      let t2 = t -. Unix.gettimeofday () in
      if t2 < 0.0 then 0.0 else t2
    with
      Heap.Empty -> (-1.0)

  let message_cmp (_, _, t1) (_, _, t2) =
    if t1 < t2 then -1 else 1

  let rec dasso soc = function
    | [] -> raise Not_found
    | (cli_soc, srv_soc, cli_addr, time)::_ when cli_soc  = soc ->
      srv_soc, cli_addr, time
    | (cli_soc, srv_soc, cli_addr, time)::_ when srv_soc  = soc ->
      cli_soc, cli_addr, time
    | _::q -> dasso soc q

  let flat l = List.fold_left (fun a (s1, s2, _, _) -> s1::s2::a) [] l

  let connect_server () =
    let addr = ADDR_INET (inet_addr_of_string !fwd_addr, !fwd_port) in
    let servsocket = socket PF_INET SOCK_STREAM 0 in
    connect servsocket addr;
    servsocket

  let send_message (m, dst_soc, _) tuples =
    let l = String.length m in
    try
      let src_soc, cli_addr, _ = dasso dst_soc tuples in
      let s = string_of_sockaddr (getpeername src_soc) in
      let d = string_of_sockaddr (getpeername dst_soc) in
      let str = Printf.sprintf "src:%s dst:%s len:%d" s d l in
        try
          let n = Unix.write dst_soc m 0 l in begin
            if n <> l then
              info_warn (str ^ ": partial write(2)");
              tuples
            end;
        with
          Unix.Unix_error _ ->
            let str = sprintf "peer %s closed"
                  (string_of_sockaddr (getpeername dst_soc))
            in info_bye cli_addr str;
            close src_soc;
            close dst_soc;
            let f (soc1, soc2, _, _) = soc1 <> dst_soc && soc2 <> dst_soc in
              List.filter f tuples
    with
      Not_found ->
        info_warn (Printf.sprintf
            "discarded %d bytes, no connection to destination" l);
        tuples

  let rec update_conn_time tuples cli_addr t =
    match tuples with
    [] -> []
    | (cli_soc, srv_soc, addr, _) :: l when addr = cli_addr ->
        (cli_soc, srv_soc, addr, t) :: l
    | e :: l ->
        e :: (update_conn_time l cli_addr t)

  let read_message queue tuples sock =
    let str = String.create !size in
    let dst_soc, cli_addr, t = dasso sock tuples in
    let len = Unix.read sock str 0 !size in
    let now = Unix.gettimeofday () in
    if len = 0 then begin
      let s = sprintf "peer %s closed" (string_of_sockaddr (getpeername sock))
      in info_bye cli_addr s;
      close sock;
      close dst_soc;
      List.filter (fun (soc1, soc2, _, _)-> soc1 <> sock && soc2 <> sock) tuples
    end else
      let m = String.sub str 0 len in
      let d = make_delay () in
      let t1 = now +. d in
      let t2 = if t1 <= t then t +. 0.001 else t1 in
      Heap.push queue (m, dst_soc, t2);
      info_msg (getpeername sock) (getpeername dst_soc) m len (t2 -. now);
      update_conn_time tuples cli_addr t2

  let accept_newclient lsock tuples =
    let (clsock, claddr) = Unix.accept lsock in
    let serv_socket = connect_server () in
    (* let s = string_of_sockaddr claddr in *)
    info_hello claddr;
    (clsock, serv_socket, claddr, 0.)::tuples

  let init_listen_serv p =
    let addr = ADDR_INET (inet_addr_any, p) in
    let servsocket = socket PF_INET SOCK_STREAM 0 in
    bind servsocket addr;
    listen servsocket 10;
    servsocket

  let rec main_loop queue tuples cl =
    let (l,_,_) = Unix.select (cl::(flat tuples)) [] [] (timenext queue) in
    let new_tuples = (match l with
      [] -> send_message (Heap.pop queue) tuples
    | t::q when t = cl -> accept_newclient cl tuples 
    | t::q -> read_message queue tuples t) in
    main_loop queue new_tuples cl
end
  
(*
  UDP functions
*)

module Udp = struct

  type connection =
    { cli_addr : Unix.sockaddr;
      cli_soc : Unix.file_descr;
      srv_addr : Unix.sockaddr;
      srv_soc : Unix.file_descr }

  type message =
    { src : Unix.sockaddr;
      dst : Unix.sockaddr;
      msg : string;
      t_in : float;
      t_out : float }

  let message_cmp m1 m2 =
    if m1.t_out < m2.t_out then -1 else 1
  let message_print m =
    Printf.printf "t_in %.3f t_out %.3f\n" m.t_in m.t_out

  (* Set a new socket to listen for udp packet on local port p*)
  let init_listen_serv p =
    let addr = ADDR_INET (inet_addr_any, p) in
    let servsocket = socket PF_INET SOCK_DGRAM 0 in
    bind servsocket addr;
    servsocket
      
  (* returns the list of all server-side sockets *)
  let all_srv_socks l =
    List.fold_left (fun ll c -> c.srv_soc :: ll) [] l

  (* when a new client arrives, with address 'cli_addr' and connected to the
  single client-side socket 'cli_soc', we create a new server-side socket,
  connect it to fwd_addr:fwd_port and add it to the list 'conns' of connections
  *)
  let conn_new cli_addr cli_soc conns =
    let srv_soc = Unix.socket PF_INET SOCK_DGRAM 0 in
    Unix.bind srv_soc (Unix.ADDR_INET (Unix.inet_addr_any, 0));
    let srv_addr = ADDR_INET (inet_addr_of_string !fwd_addr, !fwd_port) in
    Unix.connect srv_soc srv_addr;
    info_hello cli_addr;
    let c = { cli_addr = cli_addr;
              cli_soc = cli_soc;
              srv_addr = srv_addr;
              srv_soc = srv_soc } in
      c, (c :: conns)

  (* close all connections such that 'addr' is the client-side address, and all
  connections such that 'soc' is the server-side socket *)
  let conn_del addr soc conns str =
    let del c =
      if c.cli_addr = addr || c.srv_soc = soc then begin
        (try Unix.close c.srv_soc with _ -> ());
        info_bye c.cli_addr str;
        false
      end else
        true
    in List.filter del conns

  (* returns the connection whose client address is 'addr' *)
  let conn_find_cli_addr addr conns =
    try
      Some (List.find (fun c -> c.cli_addr = addr) conns)
    with
      Not_found -> None

  (* returns the connection whose server socket is 'soc' *)
  let conn_find_srv_soc soc conns =
    try
      Some (List.find (fun c -> c.srv_soc = soc) conns)
    with
      Not_found -> None

  (* given 'src_addr' and 'dst_addr' (the source and destination addresses of a
  package) returns a tuple (soc, addr, b) where soc is the destination socket,
  addr equals 'dst_addr', and b is true if the message goes to the server *)
  let rec conn_out_soc src_addr dst_addr conns =
    match conns with
    [] -> raise Not_found
    | c :: _ when c.cli_addr = src_addr && c.srv_addr = dst_addr ->
        c.srv_soc, c.srv_addr , true
    | c :: _ when c.srv_addr = src_addr && c.cli_addr = dst_addr ->
        c.cli_soc, c.cli_addr , false
    | _ :: t -> conn_out_soc src_addr dst_addr t

  (* given 'soc', 'queue', and 'conns', this function reads a package from a
  client-side socket 'soc', creates a new connection in 'conns' if the source
  address of the package is unknown, creates a new message with all the
  relevant information and puts it into the 'queue'; the function returns the
  new list of connections *)
  let read_cli_msg soc queue conns =
    let buff = String.create !size in
    let len, cli_addr = Unix.recvfrom soc buff 0 !size [] in
    let t_in = Unix.gettimeofday () in
    let d = make_delay () in
    let c, conns2 =
        match conn_find_cli_addr cli_addr conns with
        Some (c) -> c, conns
        | None -> conn_new cli_addr soc conns in
    let m = { src = cli_addr;
              dst = c.srv_addr;
              msg = String.sub buff 0 len;
              t_in = t_in;
              t_out = t_in +. d } in
    Heap.push queue m;
    info_msg m.src m.dst m.msg len d;
    conns2

  (* given the server-side 'soc', the 'queue' of messages and the list of
  connections, it reads a message from 'soc' and puts a new message into the
  'queue', deleting the connection if errors arise during the reading *)
  let read_srv_msg soc queue conns =
    let c = match conn_find_srv_soc soc conns with
        Some (c) -> c
      | None -> assert false in
    try
      let buff = String.create !size in
      let len = Unix.read soc buff 0 !size in
      let t_in = Unix.gettimeofday () in
      let d = make_delay () in
      let m = { src = c.srv_addr;
                dst = c.cli_addr;
                msg = String.sub buff 0 len;
                t_in = t_in;
                t_out = t_in +. d } in
      Heap.push queue m;
      info_msg m.src m.dst m.msg len d
    with 
      | Unix.Unix_error (c, f, _) ->
        info_warn ("error, the server probably closed: " ^
            f ^ ": " ^ (Unix.error_message c))

  (* given a client-side or server-side socket 'soc', call appropriately any of
  the previous two functions *)
  let read_msg soc queue conns = 
    match conn_find_srv_soc soc conns with
      Some _ -> read_srv_msg soc queue conns; conns
      | None -> read_cli_msg soc queue conns
    

  (* checks that the first message of the 'queue' is ready to be sent
  (producing an assertion error if not), computes the destination socket with
  conn_out_soc and sends the message, closing the connection if errors happen
  during the sending, and warning if no connection is found for the destination
  address *)
  let write_msg queue conns =
    try
      let m = Heap.pop queue in
      let s = string_of_sockaddr m.src in
      let d = string_of_sockaddr m.dst in
      let l = String.length m.msg in
      let str = Printf.sprintf "src:%s dst:%s len:%d" s d l in
      let now = Unix.gettimeofday () in
        assert (now +. 0.01 > m.t_out);
        try
          let soc, addr, is_to_serv = conn_out_soc m.src m.dst conns in
          try
            let len =
                (if is_to_serv then 
                  Unix.write soc m.msg 0 l
                else
                  Unix.sendto soc m.msg 0 l [] addr) in
            if len != (String.length m.msg) then
              info_warn (str ^ ": truncated due to partial write(2)");
          with
            Unix.Unix_error (c, f, _) ->
              info_warn (str ^ ": " ^ f ^ ": " ^ (Unix.error_message c))
        with
          Not_found ->
            info_warn (str ^ ": discarded, no route to destination")
    with
      Heap.Empty -> assert false

  (* Compute the time to the next message to send*) 
  let time_next_msg queue = 
    try
      let next_msg = Heap.peek queue in
      let t2 = next_msg.t_out -. Unix.gettimeofday () in
      if t2 < 0.0 then 0.0 else t2
    with
      Heap.Empty -> (-1.0)

  let rec main_loop queue conns cl =
    let (l,_,_) = Unix.select (cl::(all_srv_socks conns)) [] [] 
      (time_next_msg queue) in
    let new_conns = (match l with
      [] -> write_msg queue conns; conns
      | t::_ -> read_msg t queue conns) in
    main_loop queue new_conns cl
end

let main () = begin
  Random.self_init ();

  (* parse command line *)
  if (Array.length Sys.argv) <> 7 then begin
    print_endline "usage: monitor udp|tcp FORWARD_IP FORWARD_PORT LISTEN_PORT DELAY(ms) JITTER(ms)";
    exit 1;
  end;

  (* set constants *)
  size := 64 * 1024;
  if Sys.argv.(1) = "udp" then protocol_is_tcp :=false;
  fwd_addr := Sys.argv.(2);
  fwd_port := int_of_string Sys.argv.(3);
  delay := (float_of_string Sys.argv.(5)) /. 1000.;
  jitter := (float_of_string Sys.argv.(6)) /. 1000.;

  (* execute the main loop *)
  if !protocol_is_tcp then 
    Tcp.main_loop (Heap.create Tcp.message_cmp) []
      (Tcp.init_listen_serv (int_of_string Sys.argv.(4)))
  else begin
    Udp.main_loop (Heap.create Udp.message_cmp) []
      (Udp.init_listen_serv (int_of_string Sys.argv.(4)))
  end
end

let _ = Unix.handle_unix_error main ()

(* vi:ts=2:sw=2:et:
*)
