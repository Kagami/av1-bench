STILL_Y4M = $(wildcard ref/still/*.y4m)
STILL_Y4M_32 = $(patsubst ref/still/%.y4m,ref/still-32/%.y4m,$(STILL_Y4M))
STILL_AOMIVF = $(patsubst ref/still-32/%.y4m,dis/still/%.aom.ivf,$(STILL_Y4M_32))
STILL_SVTIVF = $(patsubst ref/still-32/%.y4m,dis/still/%.svt.ivf,$(STILL_Y4M_32))
STILL_JPGJPG = $(patsubst ref/still-32/%.y4m,dis/still/%.jpg.jpg,$(STILL_Y4M_32))
TIME_LOG = dis/still/time.csv
.PRECIOUS: $(STILL_Y4M_32)

VMAF_REPO_PATH ?= ../tmp/vmaf
SVTAV1_REPO_PATH ?= ../tmp/SVT-AV1

LIBAOM_VERSION := $(shell aomenc --help |& sed -nr 's/.*AOMedia Project AV1 Encoder .*-g(\w+) .*/\1/p')
LIBAOM_CPU_USED = 0
LIBAOM_CQ_LEVEL = 35

SVTAV1_VERSION := $(shell sh -c "cd '$(SVTAV1_REPO_PATH)' && git rev-parse --short HEAD")
SVTAV1_ENC_MODE = 0
SVTAV1_QP = 52

LIBJPEG_VERSION := $(shell cjpeg -version |& sed -nr 's/.*version ([^ ]+) .*/\1/p')
LIBJPEG_QUALITY = 18

define TITLE
libaom-$(LIBAOM_VERSION) (-cpu-used $(LIBAOM_CPU_USED) -cq-level $(LIBAOM_CQ_LEVEL))
SVT-AV1-$(SVTAV1_VERSION) (-enc-mode $(SVTAV1_ENC_MODE) -qp $(SVTAV1_QP))
libjpeg-$(LIBJPEG_VERSION) (-quality $(LIBJPEG_QUALITY))
endef
export TITLE

all: still

ref/still-32/%.y4m: ref/still/%.y4m
	ffmpeg -v error -i "$^" -vf "crop=floor(iw/32)*32:floor(ih/32)*32:0:0" -y "$@"

dis/still/%.aom.ivf: ref/still-32/%.y4m
	time -f "$(notdir $@)|%e" aomenc "$^" -o "$@" -q \
		--cpu-used=$(LIBAOM_CPU_USED) \
		--end-usage=q --cq-level=$(LIBAOM_CQ_LEVEL) \
		--threads=8 --row-mt=1 --tile-columns=1 --tile-rows=1 --frame-parallel=0 \
		2>>$(TIME_LOG)

dis/still/%.svt.ivf: ref/still-32/%.y4m
	time -f "$(notdir $@)|%e" SvtAv1EncApp -i "$^" -b "$@" \
		-enc-mode $(SVTAV1_ENC_MODE) -rc 0 -q $(SVTAV1_QP) \
		2>>$(TIME_LOG) >/dev/null

dis/still/%.jpg.jpg: ref/still-32/%.y4m
	ffmpeg -v error -i "$^" \
		-vf scale=in_color_matrix=bt709 \
		-sws_flags lanczos+accurate_rnd+bitexact+full_chroma_int+full_chroma_inp \
		-c ppm -f image2pipe - |\
	time -f "$(notdir $@)|%e" cjpeg -outfile "$@" \
		-quality $(LIBJPEG_QUALITY) \
		|& grep -v ^Caution >>$(TIME_LOG)

ref:
	mkdir -p ref/still
	wget -qO- https://media.xiph.org/video/derf/subset1-y4m.tar.gz |\
		tar -C ref/still --strip-components=1 -xzvf -

.venv:
	virtualenv .venv -p python2
	.venv/bin/pip install numpy scipy matplotlib pandas scikit-learn scikit-image h5py sureal

prepare: ref .venv
	mkdir -p ref/still-32 dis/still
	[ -f $(TIME_LOG) ] || echo "filename|elapsed" > $(TIME_LOG)

graph:
	PYTHONPATH=$(VMAF_REPO_PATH)/python/src ./graph.py "$$TITLE"

still: prepare $(STILL_AOMIVF) $(STILL_SVTIVF) $(STILL_JPGJPG) graph

clean:
	rm -rf ref/still-32 dis/still

distclean:
	rm -rf ref dis .venv
