# gif-peek

Read GIF87a/GIF89a dimensions and container block counts without decoding frames or printing extension data.

## Use

Requires Python 3.10+; no packages to install.

```sh
python gif_peek.py image.gif
```

Reports the logical screen, global and local color-table counts, image descriptors, extension-type counts, and bytes after the trailer. Input must be a regular file no larger than 512 MiB. The parser checks block boundaries and image rectangles but does not decode LZW data or validate extension payloads. Image descriptor count is a container count, not a guarantee that frames decode correctly.

The [GIF89a specification](https://www.w3.org/Graphics/GIF/spec-gif89a.txt) defines the block and sub-block layout used by this tool.

## License

MIT
