### Roadmap

Generally in order of priority, but priorities may change over time. You can make suggestions in the [Discussions](https://github.com/simplyequipped/pyjs8call/discussions) section of the repository.

- More extensive testing of edge use cases
- Add Wayland support for headless operation via cage (xvfb only supports x11)
- Add json and csv data export options in *propagation* module
- Bundle docs with pip installed package
- Automatic relay path discovery to specified station using QUERY CALL iteratively
- JS8Call CAT and audio device configuration via JS8Call configuration file
- Improve support for multi-band ALE-ish usage
  - *schedulemonitor* to change bands
  - *hbnetwork* for sounding on each band
  - *propagation.best_band_for_grid()* and *best_band_for_origin()* functions to analyze spot data
- Dynamic JS8Call modem speed adjustment based on SNR of specified station
