# keysight_dsox

EPICS PVAccess server for Keysight (Agilent) DSO-X oscilloscopes (may support other series).

<img src="docs/keysight_dsox.jpg" width="50%">

This module connects to a scope via VISA/SCPI, publishes waveform and settings PVs, and exposes writable control PVs for acquisition and trigger configuration.

## Features

- VISA connection to Keysight/Agilent DSO-X scopes
- PVAccess server using `epicsdev`
- Per-channel PVs for:
  - `OnOff`, `Coupling`, `VoltsPerDiv`, `VoltOffset`
  - `Waveform`, `Mean`, `Peak2Peak`, `RMS`
- Common scope PVs:
  - `timePerDiv`, `tAxis`, `samplingRate`, `trigSource`, `trigSlope`, `trigMode`, `trigLevel`
  - `acqCount`, `lostTrigs`, `scopeIDN`, `instrCmdS`/`instrCmdR`
- Triggered waveform acquisition with published time axis (`tAxis`)

## Default VISA resource

`USB0::2391::6052::MY51330356::0::INSTR`

## Requirements

- Python 3.10+
- `numpy`
- `pyvisa`
- a VISA backend (typically `pyvisa-py`)
- `epicsdev` and its EPICS/PVA dependency stack (`p4p`)

## Run

From this package directory:

`python -m keysight_dsox`

Typical usage:

`python -m keysight_dsox -r "USB0::2391::6052::MY51330356::0::INSTR" -d keysight -i 0 -C 4 -v`

This creates PVs with prefix `<device><index>:` (default: `keysight0:`).

## Command-line options

- `-r, --resource` VISA resource string
- `-d, --device` device prefix base name
- `-i, --index` device index appended to prefix
- `-C, --channels` number of channels to expose
- `-l, --list` directory where generated PV list is saved
- `-a, --autosave` autosave control (optional argument)
- `-c, --recall` disable restoring PV values from autosave cache
- `-p, --putlogPV` PV name for put logging
- `-v, --verbose` increase verbosity (`-vv` for more)

## Example PV names

With default prefix `keysight0:`:

- `keysight0:scopeIDN`
- `keysight0:trigState`
- `keysight0:tAxis`
- `keysight0:c01Waveform`
- `keysight0:c01VoltsPerDiv`
- `keysight0:c01VoltOffset`
- `keysight0:c01OnOff`

## Phoebus screen

A simple screen generator is included:

- Source: `screens/generate_simplescope.py`
- Output: `screens/simplescope.bob`

Generate with:

`python screens/generate_simplescope.py --prefix 'keysight0:'`

## Notes

- On startup, the server reads selected scope settings and adopts them into PVs.
- Waveforms are acquired on trigger detection and published with channel statistics.
- If all channels are set `Off`, channel 1 is used as a fallback acquisition source.
