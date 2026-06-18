# logikit — convenience targets. Generation/check/sim need only Python (stdlib).
# Rendering needs $LOGISIM_JAR (PNG) and/or lualatex + a CJK font (breadboard PDF).

PY ?= python3
SCALE ?= 4

.PHONY: doctor test examples check sim figures wiring render clean help

help:
	@echo "make test       run the unit test suite (pure stdlib; no extra install)"
	@echo "make doctor     check which capabilities are available in this environment"
	@echo "make examples   generate example .circ + run connectivity check + truth tables"
	@echo "make figures    render the example schematics to build/*.png (needs LOGISIM_JAR)"
	@echo "make wiring     build the example breadboard PDF (needs lualatex + CJK font)"
	@echo "make clean      remove build artifacts"

test:
	$(PY) -m unittest discover -s tests -v

doctor:
	$(PY) -m logikit.doctor

examples:
	$(PY) -m examples.circuits

check:
	$(PY) -m logikit.check --dir=build mux2_nand and3_nand ring_osc_nand

sim:
	$(PY) -m logikit.sim --dir=build mux2_nand and3_nand ring_osc_nand

figures: examples
	./render/render.sh build/mux2_nand_fig.circ     build/mux2_nand.png     $(SCALE)
	./render/render.sh build/and3_nand_fig.circ     build/and3_nand.png     $(SCALE)
	./render/render.sh build/ring_osc_nand_fig.circ build/ring_osc_nand.png $(SCALE)

wiring:
	$(PY) -m examples.breadboard

render: figures wiring

clean:
	rm -rf build render/LogiRender.class **/__pycache__ */**/__pycache__
