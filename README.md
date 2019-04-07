# av1-bench

AV1 encoders benchmarks for specific use-cases.

## Still-image

Comparision of [libaom](https://aomedia.googlesource.com/aom/) and
[SVT-AV1](https://github.com/OpenVisualCloud/SVT-AV1) for still-image coding on
subset1 from [derf's collection](https://media.xiph.org/video/derf/). JPEG
files are also encoded with libjpeg for the reference.

![](graphs/still1.png)

## Usage

Setup make, FFmpeg, VMAF, libaom, SVT-AV1, libjpeg and run:

```
make
```

## TODO

* Add more metrics (PSNR, SSIM, etc.)
* Compare at different quality/speed

## License

[CC0](COPYING).
