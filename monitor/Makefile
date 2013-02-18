
OBJS=monitor.cmo
DEPS:=$(patsubst %.cmo,%.d,$(OBJS))

all : monitor

monitor : $(OBJS)
	ocamlc -o $@ unix.cma $^ 

udp : udp.ml
	ocamlc -o $@ unix.cma udp.ml

clean :
	rm -f udp monitor *.cmo *.cmi *.cmx *.d *.o


.SUFFIXES: .mli .mll .mly .ml .cmo .cmi .cmx .d
.ml.cmo :
	ocamlc -c $(OFLAGS) $(INCLUDES) $<
.mli.cmi :
	ocamlc -c $(OFLAGS) $(INCLUDES) $<
.ml.cmi :
	ocamlc -c $(OFLAGS) $(INCLUDES) $<
.ml.cmx :
	ocamlopt -c $(OFLAGS) $(INCLUDES) $<
.mll.ml :
	ocamllex $(OLEXFLAGS) $<
.mly.ml :
	ocamlyacc $(OYACCFLAGS) $<
.mly.mli:
	ocamlyacc $(OYACCFLAGS)
.ml.d :
	ocamldep $< > $@

-include $(DEPS)
