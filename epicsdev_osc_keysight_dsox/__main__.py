"""EPICS PVAccess server for Keysight DSO-X oscilloscopes."""
# pylint: disable=invalid-name
__version__ = 'v0.0.3 26-08-25'# No Threadlock, because it is single-threaded. Y axis min/max fixed to -4.0/4.0 
import sys
import time
from time import perf_counter as timer
import argparse
from dataclasses import dataclass

import numpy as np
import pyvisa as visa
from pyvisa.errors import VisaIOError

from epicsdev import epicsdev as edev

MAX_CHANNELS = 8
# Keysight DSO-X family typically uses 10 horizontal divisions.
NDIVSX = 10
DEFAULT_VISA_RESOURCE = 'USB0::2391::6052::MY51330356::0::INSTR'

IF_CHANGED = True
ElapsedTime = {
    'trigger_detection': 0.0,
    'acquire_wf': 0.0,
    'publish_wf': 0.0,
}

@dataclass(slots=True)
class C_:
    """Namespace for module state."""
    scope = None
    scpi = {}
    PvDefs = []
    readSettingQuery = ''
    previousScopeParametersQuery = ''
    channelsEnabled = []
    trigTime = 0.0
    trigState = ''
    prevXpreamble = (0., 0., 0., 0.)# xorig, xincr, xref, recLength
    prevYpreamble = [(0., 0., 0., 1.)]*MAX_CHANNELS # yorig, yincr, yref, voltsPerDiv

pargs = None

def myPVDefs():
    """PV definitions for Keysight DSO-X."""
    F, T, U, LL, LH, SCPI, SET = 'features', 'type', 'units', 'limitLow', 'limitHigh', 'scpi', 'setter'
    alarm = {'valueAlarm': {'lowAlarmLimit': -9.0, 'highAlarmLimit': 9.0}}

    pvDefs = [
        ['visaResource', 'VISA resource used to access the oscilloscope', pargs.resource],
        ['scopeIDN', 'Response to *IDN? query', 'N/A'],
        ['dateTime', 'Scope date & time', 'N/A'],# {SCPI: "SYSTem:DATE?;:SYSTem:TIME"}],
        ['acqCount', 'Number of accepted waveform', 0, {T: 'u32'}],
        ['lostTrigs', 'Number of lost triggers', 'N/A'],
        ['instrCmdS', 'Execute custom SCPI command', '*IDN?', {F: 'W', SET: set_instrCmdS}],
        ['instrCmdR', 'Reply to custom SCPI command', ''],

        ['recLengthS', 'Requested waveform points, Not supported on Keysight DSO-X', 'N/A'],
        ['recLengthR', 'Actual waveform points', 0, {T: 'u32'}],
        ['samplingRate', 'Sampling rate', 0.0, {U: 'Hz'}],
        ['timePerDiv', f'Horizontal scale (1/{NDIVSX} of full scale)', 1e-3,
            {F: 'W', U: 'S/div', SCPI: ':TIMebase:SCALe', SET: set_scpi}],
        ['tAxis', 'Horizontal axis array', [0.0], {U: 'S'}],

        ['trigger', 'Force trigger action', ['Trigger', 'Force!'], {F: 'WD', SET: set_trigger}],
        ['trigState', 'Current trigger state: +1 triggered, +0 not triggered', '?', {SCPI: ':TER'}],
        ['trigMode', 'Trigger sweep mode', ['NORM', 'AUTO'],
            {F: 'WD', SCPI: ':TRIGger:SWEep', SET: set_scpi}],
        ['trigDelay', 'Trigger horizontal position', 0.0,
            {F: 'W', U: 'S', SCPI: ':TIMebase:POSition', SET: set_scpi}],
        ['trigSource', 'Trigger source', ['CHAN1', 'CHAN2', 'CHAN3', 'CHAN4', 'LINE', 'EXT'],
            {F: 'WD', SCPI: ':TRIGger:EDGE:SOURce', SET: set_scpi}],
        ['trigSlope', 'Trigger slope', ['POS', 'NEG', 'EITH'],
            {F: 'WD', SCPI: ':TRIGger:EDGE:SLOPe', SET: set_scpi}],
        ['trigLevel', 'Trigger level', 0.0,
            {F: 'W', U: 'V', SCPI: ':TRIGger:EDGE:LEVel', SET: set_scpi}],

        ['setupSlot', 'Setup slot number N used by save/restore', 1,
            {F: 'W', T: 'u32', LL: 1, LH: 10}],
        ['saveSetup', 'Save current scope setup to slot N', ['Save'],
            {F: 'WD', SET: set_saveSetup}],
        ['restoreSetup', 'Recall scope setup from slot N', ['Restore'],
            {F: 'WD', SET: set_restoreSetup}],

        ['timing', 'Performance timing', [0.0], {U: 'S'}],
    ]

    # Important: use templates with plain initial values (no SharedPV here).
    channelTemplates = [
        ['c<n>OnOff', 'Enable/disable channel', ['0', '1'],
            {F: 'WD', SCPI: ':CHANnel<n>:DISPlay', SET: set_scpi}],
        ['c<n>Coupling', 'Channel keysight_dsox/__main__.pycoupling', ['DC', 'AC'],
            {F: 'WD', SCPI: ':CHANnel<n>:COUPling', SET: set_scpi}],
        ['c<n>VoltsPerDiv', 'Vertical scale', 1e-3,
            {F: 'W', U: 'V/div', SCPI: ':CHANnel<n>:SCALe', SET: set_scpi, LL: 1e-3, LH: 20.0}],
        ['c<n>Offset', 'Vertical negative offset', 0.0,
            {F: 'W', U: 'div', SCPI: ':CHANnel<n>:OFFSet', SET: set_scpi}],
        ['c<n>Waveform', 'Waveform array', [0.0], {U: 'V'}],
        ['c<n>Mean', 'Mean of waveform', 0.0, {U: 'V'}],
        ['c<n>Peak2Peak', 'Peak-to-peak amplitude', 0.0, {U: 'V', **alarm}],
        ['c<n>RMS', 'RMS of waveform', 0.0, {U: 'V'}],
    ]

    # Generate channel PVs for each channel number.
    for ch in range(pargs.channels):
        for pvdef in channelTemplates:
            p = pvdef.copy()
            p[0] = p[0].replace('<n>', f'{ch+1:02d}')
            if len(p) > 3 and 'scpi' in p[3]:
                p[3] = p[3].copy()
                p[3]['scpi'] = p[3]['scpi'].replace('<n>', str(ch + 1))
            pvDefs.append(p)
    return pvDefs

def handle_exception(where):
    """Log exception and keep server alive when possible."""
    edev.printe(f'{where}: {sys.exc_info()[1]}')

def scopeCmd(cmd: str):
    """Send a command to scope and optionally return reply."""
    reply = None
    if '?' in cmd:
        reply = C_.scope.query(cmd).strip()
    else:
        C_.scope.write(cmd)
    return reply

def set_instrCmdS(cmd, *_):
    """Setter for arbitrary SCPI command PV."""
    cmd = str(cmd)
    edev.publish('instrCmdR', '')
    try:
        r = scopeCmd(cmd)
        if r is not None:
            edev.publish('instrCmdR', r)
    except VisaIOError:
        handle_exception(f'in set_instrCmdS({cmd})')

def set_trigger(value, *_):
    """Setter for trigger PV."""
    if str(value) == 'Force!':
        try:
            scopeCmd(':TFORce')
        except VisaIOError:
            handle_exception('in set_trigger')
        finally:
            edev.publish('trigger', 'Trigger')

def _setup_slot() -> int:
    """Return validated setup slot number N."""
    try:
        slot = int(edev.pvv('setupSlot'))
    except (TypeError, ValueError):
        slot = 1
    return max(1, min(10, slot))

def set_saveSetup(value, *_):
    """Save instrument setup into slot N."""
    #print(f'set_saveSetup called with value={value}')
    slot = _setup_slot()
    try:
        scopeCmd(f':SAVE:SETup:STARt {slot}')
        edev.printi(f'Saved setup to slot {slot}')
    except VisaIOError:
        handle_exception(f'in set_saveSetup({slot})')

def set_restoreSetup(value, *_):
    """Recall instrument setup from slot N."""
    #print(f'set_restoreSetup called with value={value}')    
    slot = _setup_slot()
    try:
        scopeCmd(f':RECall:SETup:STARt {slot}')
        edev.printi(f'Restored setup from slot {slot}')
    except VisaIOError:
        handle_exception(f'in set_restoreSetup({slot})')

def set_scpi(value, pv, *_):
    """Generic setter for SCPI-backed PVs."""
    pvname = str(pv.name)
    edev.printv(f'set_scpi called for {pvname} with value {value}')
    scpi = C_.scpi.get(pvname)
    if scpi is None:
        edev.printw(f'No SCPI associated with {pvname}')
        return

    # If the PV is an OnOff type, clear the waveform and related PVs when turned off.
    if 'OnOff' in pvname:
        if value == '0':
            edev.publish(f'{pvname[:3]}Waveform', [0.])
            # edev.publish(f'{pvname[:3]}Peak2Peak', 0.)
            # edev.publish(f'{pvname[:3]}Mean', 0.)
            # edev.publish(f'{pvname[:3]}RMS', 0.)
    try:
        scopeCmd(f'{scpi} {value}')
        edev.printv(f'Sent SCPI command: {scpi} {value}')
    except VisaIOError:
        handle_exception(f'in set_scpi for {pvname}')

def serverStateChanged(newState: str):
    """Called by epicsdev when server PV changes."""
    if newState == 'Start':
        edev.printi('Start requested')
        try:
            configure_scope()
            adopt_local_setting(C_.readSettingQuery)
            scopeCmd(':RUN')
        except VisaIOError:
            handle_exception('in serverStateChanged(Start)')
            edev.set_server('Stop')
    elif newState == 'Stop':
        edev.printi('Stop requested')
    elif newState == 'Exit':
        edev.printi('Exit requested')

def configure_scope():
    """Configure waveform transfer format according to Keysight programming style."""
    C_.scope.write(':WAVeform:FORMat WORD')
    C_.scope.write(':WAVeform:BYTeorder LSBFirst')
    C_.scope.write(':WAVeform:UNSigned 1')
    C_.scope.write(':WAVeform:POINts:MODE RAW')

def init_visa():
    """Initialize VISA resource and validate instrument type."""
    try:
        rm = visa.ResourceManager('@py')
    except ModuleNotFoundError as e:
        edev.printe(f'Failed to initialize VISA backend: {e}')
        sys.exit(1)

    resource = pargs.resource.upper()
    edev.printi(f'Opening resource {resource}')
    try:
        C_.scope = rm.open_resource(resource)
    except VisaIOError as e:
        edev.printe(f'Could not open VISA resource {resource}: {e}')
        sys.exit(1)

    C_.scope.timeout = 3000
    C_.scope.read_termination = '\n'
    C_.scope.write_termination = '\n'

    try:
        #C_.scope.clear()
        idn = C_.scope.query('*IDN?').strip()
    except VisaIOError as e:
        edev.printe(f'VISA I/O error during initialization: {e}')
        sys.exit(1)

    edev.publish('scopeIDN', idn)
    edev.printi(f'IDN: {idn}')
    if ('KEYSIGHT' not in idn.upper()) and ('AGILENT' not in idn.upper()):
        edev.printw('Connected instrument does not identify as Keysight/Agilent DSO-X')

def make_readSettingQuery():
    """Build a compact multi-query SCPI for PVs with SCPI mapping."""
    C_.scpi = {}
    for pvdef in C_.PvDefs:
        pvname = pvdef[0]
        extra = pvdef[3] if len(pvdef) > 3 else {}
        scpi = extra.get('scpi')
        if scpi:
            C_.scpi[pvname] = scpi
    C_.readSettingQuery = '?;'.join(C_.scpi.values()) + '?'
    #edev.printi(f'readSettingQuery: {C_.readSettingQuery}')

def _convert_value(current_value, text_value: str):
    """Convert SCPI textual value to PV Python type."""
    text_value = text_value.strip()
    raw = current_value.raw.value if hasattr(current_value, 'raw') else current_value
    if isinstance(raw, str):
        return text_value
    if isinstance(raw, int):
        return int(float(text_value))
    if isinstance(raw, float):
        return float(text_value)
    return text_value

def adopt_local_setting(query):
    """Read current scope settings and update associated PVs."""
    #print(f'adopt_local_setting called with query: {query}')
    try:
        values = C_.scope.query(query).split(';')
        for pvname, v in zip(C_.scpi.keys(), values):
            current = edev.pvobj(pvname).current()
            converted = _convert_value(current, v)
            #print(f'Updating PV {pvname} with value {converted} from scope response {v}')
            edev.publish(pvname, converted, IF_CHANGED)
    except VisaIOError:
        handle_exception(f'in adopt_local_setting for query {query}')

    update_scopeParameters()
    refresh_channelsEnabled()

def refresh_channelsEnabled():
    """Refresh list of channels to read."""
    C_.channelsEnabled = []
    for ch in range(pargs.channels):
        onoff = str(edev.pvv(f'c{ch+1:02d}OnOff')).strip().upper()
        if onoff in ('1', 'ON', 'TRUE'):
            C_.channelsEnabled.append(ch + 1)
    if not C_.channelsEnabled:
        C_.channelsEnabled = [1]

def update_scopeParameters():
    """Update scope parameters, which may have changed due to user interaction on the scope."""
    dateTime = scopeCmd("SYSTem:DATE?;:SYSTem:TIME?")
    dateTime = dateTime.replace('+', '').replace(';', ',')
    y, m, d, h, min_, s = dateTime.split(',')
    dateTime = f"{y}-{m}-{d} {h}:{min_}:{s}"
    edev.publish('dateTime', dateTime)
    return

def trigger_is_detected():
    """Check trigger state and decide when to read waveform."""
    try:
        r = scopeCmd(':TER?')
        if r != C_.trigState:
            C_.trigState = r
            edev.publish('trigState', C_.trigState)
    except VisaIOError:
        handle_exception('in trigger_is_detected')
        return False
    #print(f'Trigger state: {type(trigState),trigState}')
    return C_.trigState=='+1'

def acquire_waveforms():
    """Acquire waveform data for enabled channels and publish PVs."""
    ts_total = timer()
    ts_publish = 0.0

    refresh_channelsEnabled()

    C_.trigTime = time.time()# TODO: get trigtime from scope if possible

    edev.publish('acqCount', edev.pvv('acqCount') + 1)

    try:
        C_.scope.write(':STOP')
    except VisaIOError:
        handle_exception('stopping scope in acquire_waveforms')
        return

    recLength = 0
    for ch in C_.channelsEnabled:
        try:
            C_.scope.write(f':WAVeform:SOURce CHANnel{ch}')
            pre = C_.scope.query(':WAVeform:PREamble?').strip().split(',')
            data = C_.scope.query_binary_values(':WAVeform:DATA?', datatype='H',
                container=np.array)

            if len(pre) < 10:
                edev.printw(f'Unexpected preamble for CH{ch}: {pre}')
                continue
            edev.printvv(f'received waveform for CH{ch}: {len(data)} points')
            #print(f'CH{ch} preamble: {pre}')

            # Update tAxis PV if waveform geometry changed.
            xincr, xorig, xref = np.array(np.float32(pre[4:7]), dtype=np.float32)
            recLength = len(data)
            if (xincr, xorig, xref, recLength) != C_.prevXpreamble:
                #print(f'Waveform geometry changed: xincr={xincr}, xorig={xorig}, xref={xref}, recLength={recLength}')
                taxis = (np.arange(len(data)) - xref) * xincr + xorig
                edev.publish('tAxis', taxis.tolist(), t=C_.trigTime)
                edev.publish('samplingRate', 1.0 / xincr, t=C_.trigTime, ifChanged=True)
                r = scopeCmd(':TIMebase:SCALe?')
                edev.publish('timePerDiv', float(r), t=C_.trigTime, ifChanged=True)
                r = scopeCmd(':TIMebase:POSition?')
                edev.publish('trigDelay', float(r), t=C_.trigTime, ifChanged=True)
                edev.publish('recLengthR', recLength, t=C_.trigTime, ifChanged=True)
                C_.prevXpreamble = (xincr, xorig, xref, recLength)

            # update voltsPerDiv PV if waveform geometry changed.
            # Note: Keysight DSO-X preamble does not provide enough info for voltsPerDiv, so we read it from the scope.
            yincr, yorig, yref = np.array(np.float32(pre[7:10]), dtype=np.float32)
            ich = ch - 1
            if yincr != C_.prevYpreamble[ich][0]:
                r = scopeCmd(f':CHANnel{ch}:SCALe?')
                voltsPerDiv = float(r) if r is not None else 1.0
                #print(f'CH{ch} yincr changed: {yincr} from {C_.prevYpreamble[ich][0]}, yorig={yorig}, yref={yref}, voltsPerDiv={voltsPerDiv}')
                edev.publish(f'c{ch:02d}VoltsPerDiv', voltsPerDiv, t=C_.trigTime)
                C_.prevYpreamble[ich] = (yincr, yorig, yref, voltsPerDiv)
            voltsPerDiv = C_.prevYpreamble[ich][3]
            #print(f'CH{ch} preamble: yincr={yincr}, yorig={yorig}, yref={yref}')

            samplesv = (data - yref) * yincr # convert to divisions
            #print(f"mean data: {data.mean()}, samplesv: {samplesv.mean()}")
            samplesd = (samplesv/voltsPerDiv).astype(np.float32)
            t0 = timer()
            edev.publish(f'c{ch:02d}Waveform', samplesd, t=C_.trigTime)
            edev.publish(f'c{ch:02d}Peak2Peak', float(np.ptp(samplesv)), t=C_.trigTime)
            edev.publish(f'c{ch:02d}Mean', float(np.mean(samplesv)), t=C_.trigTime)
            edev.publish(f'c{ch:02d}RMS', float(np.std(samplesv)), t=C_.trigTime)
            edev.publish(f'c{ch:02d}Offset', yorig, t=C_.trigTime, ifChanged=True)
            ts_publish += timer() - t0

        except VisaIOError:
            handle_exception(f'in acquire_waveforms channel {ch}')
            break

    try:
        C_.scope.write(':RUN')
    except VisaIOError:
        handle_exception('restarting scope in acquire_waveforms')

    ElapsedTime['publish_wf'] = round(ts_publish, 6)
    ElapsedTime['acquire_wf'] = round(timer() - ts_total, 6)

def periodic_update():
    """Infrequent updates."""
    update_scopeParameters()
    edev.publish('timing', [
        ElapsedTime['trigger_detection'],
        ElapsedTime['acquire_wf'],
        ElapsedTime['publish_wf'],
    ])

def poll():
    """Device polling function."""
    if trigger_is_detected():
        acquire_waveforms()

def init():
    """Module initialization."""
    init_visa()
    make_readSettingQuery()
    edev.publish('VERSION', __version__)

#``````````````````Main entry point```````````````````
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=__version__,
    )

    parser.add_argument('-a', '--autosave', nargs='?', default='', help=
        'Autosave control. If not given, autosave is enabled with default directory.')
    parser.add_argument('-c', '--recall', action='store_false', help=
        'If given: do not restore initial PV values from autosave cache.')
    parser.add_argument('-C', '--channels', type=int, default=4, help=
        'Number of scope channels to expose as PVs.')
    parser.add_argument('-d', '--device', default='keysight', help=
        'Device name, the PV prefix is <device><index>:')
    parser.add_argument('-i', '--index', default='0', help=
        'Device index, the PV prefix is <device><index>:')
    parser.add_argument('-l', '--list', nargs='?', help=
        'Directory to save the full list of generated PVs.')
    parser.add_argument('-p', '--putlogPV', nargs='?', default='', help=
        'PV name for logging put operations. Empty means default putlog:dump.')
    parser.add_argument('-r', '--resource', default=DEFAULT_VISA_RESOURCE, help=
        'VISA resource string for the scope.')
    parser.add_argument('-v', '--verbose', action='count', default=0, help=
        'Increase verbosity (-vv for more).')

    pargs = parser.parse_args()
    if pargs.putlogPV == '':
        pargs.putlogPV = 'putlog:dump'

    pargs.prefix = f'{pargs.device}{pargs.index}:'
    C_.PvDefs = myPVDefs()

    PVs = edev.init_epicsdev(
        pargs.prefix,
        C_.PvDefs,
        pargs.verbose,
        serverStateChanged,
        pargs.list,
        pargs.autosave,
        pargs.recall,
        pargs.putlogPV,
    )

    init()
    edev.set_server('Start')

    server = edev.Server(providers=[PVs])
    edev.printi(
        f'Server for {pargs.prefix} started. Sleeping per cycle: {repr(edev.pvv("sleep"))} S.'
    )

    while True:
        state = edev.serverState()
        if state.startswith('Exit'):
            break
        if not state.startswith('Stop'):
            poll()
        if not edev.sleep():
            periodic_update()

    edev.printi('Server is exited')
