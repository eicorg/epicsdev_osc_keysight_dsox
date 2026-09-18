"""Generate a simple Phoebus screen for epicsdev-based oscilloscopes"""
__version__ = 'v3.0.3 2026-09-16'# Min added, better row spacing.

import argparse
from pathlib import Path

import phoebusgen.screen
import phoebusgen.widget

DEFAULT_PREFIX = "$(DEV):"

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=__version__)
    parser.add_argument("-t", "--title", default="SimpleScope", help="Screen title")
    parser.add_argument("prefix", default=DEFAULT_PREFIX, help=
"PV prefix used for all widget PV names. If not specified, the prefix is `$(DEV):`, it could be defined in screen macros.",
    )
    return parser.parse_args()

def main() -> None:
    pargs = _parse_args()
    prefix = pargs.prefix

    screen = phoebusgen.screen.Screen(pargs.title, "simplescope.bob")
    screen.width(980)
    screen.height(360)

    w = phoebusgen.widget
    widgets = {
        "SimpleScope": w.Label("title", "SimpleScope", 20, 10, 220, 30),
        "scopIDN":  w.TextUpdate("scopeIDN", f"{prefix}scopeIDN", 120, 10, 270, 20),
        "dateTime": w.TextUpdate("dateTime", f"{prefix}dateTime", 410, 10, 70, 20),
        "acquire": w.ComboBox("acquire", f"{prefix}acquire", 560, 10, 90, 20),
        "setup": w.ComboBox("setup", f"{prefix}setup", 660, 10, 80, 20),
    }
    y = 38
    widgets.update({
        "srvStatus_lbl": w.Label("srvStatus_lbl", "Server:", 20, y, 100, 20),
        "srvStatus": w.TextUpdate("srvStatus", f"{prefix}status", 70, y, 790, 20),
    })
    y += 22
    widgets.update({
        "run_lbl": w.Label("run_lbl", "Server:", 20, y, 70, 20),
        "server": w.ComboBox("server", f"{prefix}server", 100, y, 80, 20),
        "sleep_lbl": w.Label("sleep_lbl", "Sleep:", 190, y, 40, 20),
        "sleep": w.TextEntry("sleep", f"{prefix}sleep", 240, y, 60, 20),
        "cycleTime": w.TextUpdate("cycleTime", f"{prefix}cycleTime", 310, y, 60, 20),
        "acq_lbl": w.Label("acq_lbl", "Acq Count:", 380, y, 80, 20),
        "acqCount": w.TextUpdate("acqCount", f"{prefix}acqCount", 460, y, 60, 20),
        "lost_lbl": w.Label("lost_lbl", "Lost Trigs:", 540, y, 70, 20),
        "lostTrigs": w.TextUpdate("lostTrigs", f"{prefix}lostTrigs", 620, y, 60, 20),
    })
    y += 22
    widgets.update({
        "time_lbl": w.Label("time_lbl", "Time/Div:", 10, y, 70, 20),
        "timePerDiv": w.TextEntry("timePerDiv", f"{prefix}timePerDiv", 80, y, 110, 20),
        "reclen_lbl": w.Label("reclen_lbl", "RecLength:", 210, y, 80, 20),
        "reclenR": w.TextUpdate("reclenR", f"{prefix}recLengthR", 290, y, 70, 20),
        "reclenS": w.TextEntry("reclenS", f"{prefix}recLengthS", 370, y, 70, 20),
        "samplingRate_lbl": w.Label("samplingRate_lbl", "SRate:", 460, y, 60, 20),
        "samplingRate": w.TextUpdate("samplingRate", f"{prefix}samplingRate", 520, y, 80, 20),
    })
    widgets["timePerDiv"].format('Exponential')
    widgets["timePerDiv"].precision(1)
    widgets["reclenR"].format('Decimal')
    widgets["reclenR"].precision(0)
    widgets["reclenS"].format('Decimal')
    widgets["reclenS"].precision(0)
    widgets["samplingRate"].format('Exponential')
    widgets["samplingRate"].precision(1)
    y += 22
    widgets.update({
        #"trigSource_lbl": w.Label("trigSource_lbl", "Trigger:", 20, y, 90, 20),
        "state_lbl": w.Label("state_lbl", "Trig State:", 10, y, 70, 20),
        "trigState": w.TextUpdate("trigState", f"{prefix}trigState", 80, y, 40, 20),
        "trigSource": w.ComboBox("trigSource", f"{prefix}trigSource", 140, y, 70, 20),  
        "trig_lvl_lbl": w.Label("trig_lvl_lbl", "Level:", 230, y, 40, 20),
        "trigLevel": w.TextEntry("trigLevel", f"{prefix}trigLevel", 280, y, 70, 20),
        "trigSlope_lbl": w.Label("trigSlope_lbl", "Slope:", 360, y, 60, 20),
        "trigSlope": w.ComboBox("trigSlope", f"{prefix}trigSlope", 420, y, 70, 20),
        "trigMode_lbl": w.Label("trigMode_lbl", "Mode:", 500, y, 60, 20),
        "trigMode": w.ComboBox("trigMode", f"{prefix}trigMode", 560, y, 80, 20),
        "trigDelay_lbl": w.Label("trigDelay_lbl", "Delay:", 660, y, 60, 20),
        "trigDelay": w.TextEntry("trigDelay", f"{prefix}trigDelay", 720, y , 80, 20),
    })
    y += 22
    widgets.update({
        #"wf_lbl": w.Label("wf_lbl", "Waveforms", 10, 110, 960, 420),
        "wf_plot": w.XYPlot("wf_plot", 10, y, 930, 450),
    })
    y += 450
    widgets.update({
        "vpd_lbl": w.Label("vpd_lbl", "Volts/Div:", 10, y, 70, 20),
        "c01VoltsPerDiv": w.TextEntry("c01VoltsPerDiv", f"{prefix}c01VoltsPerDiv", 90, y, 100, 20),
        "c02VoltsPerDiv": w.TextEntry("c02VoltsPerDiv", f"{prefix}c02VoltsPerDiv", 210, y, 100, 20),
        "c03VoltsPerDiv": w.TextEntry("c03VoltsPerDiv", f"{prefix}c03VoltsPerDiv", 330, y, 100, 20),
        "c04VoltsPerDiv": w.TextEntry("c04VoltsPerDiv", f"{prefix}c04VoltsPerDiv", 450, y, 100, 20),
    })
    y += 25
    widgets.update({
        "voff_lbl": w.Label("voff_lbl", "Offset:", 10, y, 70, 20),
        "c01Offset": w.TextEntry("c01Offset", f"{prefix}c01Offset", 90, y, 100, 20),
        "c02Offset": w.TextEntry("c02Offset", f"{prefix}c02Offset", 210, y, 100, 20),
        "c03Offset": w.TextEntry("c03Offset", f"{prefix}c03Offset", 330, y, 100, 20),
        "c04Offset": w.TextEntry("c04Offset", f"{prefix}c04Offset", 450, y, 100, 20),
    })
    y += 25
    widgets.update({
        "OnOff_lbl": w.Label("OnOff_lbl", "On/Off:", 10, y, 70, 20),
        "c01OnOff": w.BooleanButton("c01OnOff", f"{prefix}c01OnOff", 90, y, 100, 20),
        "c02OnOff": w.BooleanButton("c02OnOff", f"{prefix}c02OnOff", 210, y, 100, 20),
        "c03OnOff": w.BooleanButton("c03OnOff", f"{prefix}c03OnOff", 330, y, 100, 20),
        "c04OnOff": w.BooleanButton("c04OnOff", f"{prefix}c04OnOff", 450, y, 100, 20),
    })
    y += 25
    widgets.update({
        "min_lbl": w.Label("min_lbl", "Min [V]:", 10, y, 70, 20),
        "c01Min": w.TextUpdate("c01Min", f"{prefix}c01Min", 90, y, 100, 20),
        "c02Min": w.TextUpdate("c02Min", f"{prefix}c02Min", 210, y, 100, 20),
        "c03Min": w.TextUpdate("c03Min", f"{prefix}c03Min", 330, y, 100, 20),
        "c04Min": w.TextUpdate("c04Min", f"{prefix}c04Min", 450, y, 100, 20),
    })
    y += 25
    widgets.update({
        "mean_lbl": w.Label("mean_lbl", "Mean [V]:", 10, y, 70, 20),
        "c01Mean": w.TextUpdate("c01Mean", f"{prefix}c01Mean", 90, y, 100, 20),
        "c02Mean": w.TextUpdate("c02Mean", f"{prefix}c02Mean", 210, y, 100, 20),
        "c03Mean": w.TextUpdate("c03Mean", f"{prefix}c03Mean", 330, y, 100, 20),
        "c04Mean": w.TextUpdate("c04Mean", f"{prefix}c04Mean", 450, y, 100, 20),
    })
    y += 25
    widgets.update({
        "rms_lbl": w.Label("rms_lbl", "RMS [V]:", 10, y, 70, 20),
        "c01RMS": w.TextUpdate("c01RMS", f"{prefix}c01RMS", 90, y, 100, 20),
        "c02RMS": w.TextUpdate("c02RMS", f"{prefix}c02RMS", 210, y, 100, 20),
        "c03RMS": w.TextUpdate("c03RMS", f"{prefix}c03RMS", 330, y, 100, 20),
        "c04RMS": w.TextUpdate("c04RMS", f"{prefix}c04RMS", 450, y, 100, 20),
    })
    y += 25
    widgets.update({
        "p2p_lbl": w.Label("p2p_lbl", "P2P [V]:", 10, y, 70, 20),
        "c01Peak2Peak": w.TextUpdate("c01Peak2Peak", f"{prefix}c01Peak2Peak", 90, y, 100, 20),
        "c02Peak2Peak": w.TextUpdate("c02Peak2Peak", f"{prefix}c02Peak2Peak", 210, y, 100, 20),
        "c03Peak2Peak": w.TextUpdate("c03Peak2Peak", f"{prefix}c03Peak2Peak", 330, y, 100, 20),
        "c04Peak2Peak": w.TextUpdate("c04Peak2Peak", f"{prefix}c04Peak2Peak", 450, y, 100, 20),
    })
    y += 25
    widgets.update({
        "scpi_lbl": w.Label("scpi_lbl", "SCPI:", 10, y, 50, 20),
        "instrCmdS": w.TextEntry("instrCmdS", f"{prefix}instrCmdS", 50, y, 200, 20),
        "instrCmdR": w.TextUpdate("instrCmdR", f"{prefix}instrCmdR", 260, y, 550, 20),
    })

    # Populate combo boxes with items.
    for item in "Start, Stop, Clear, Exit, Started, Stopped, Exited".split(", "):
        widgets["server"].item(item)
    for item in "POS, NEG, EITH".split(", "):
        widgets["trigSlope"].item(item)
    for item in "NORM, AUTO".split(", "):
        widgets["trigMode"].item(item)

    # Set formats and precision for numeric widgets.
    widgets["sleep"].precision(2)
    widgets["acqCount"].format('Decimal')
    widgets["acqCount"].precision(0)
    widgets["lostTrigs"].format('Decimal')
    widgets["lostTrigs"].precision(0)
    widgets["trigLevel"].format('Engineering')
    widgets["trigLevel"].precision(3)
    widgets["trigDelay"].format('Exponential')
    for wname in ["c01Mean", "c02Mean", "c03Mean", "c04Mean", "c01RMS", "c02RMS", "c03RMS", "c04RMS", "c01Peak2Peak", "c02Peak2Peak", "c03Peak2Peak", "c04Peak2Peak"]:
        widgets[wname].format('Engineering')
        widgets[wname].precision(3)
    for item in "CHAN1, CHAN2, CHAN3, CHAN4, EXT, LINE".split(", "):
        widgets["trigSource"].item(item)

    # Configure waveform traces using tAxis as x and channel waveform as y.
    #plot = next(w for w in widgets if w.get_element_value("name") == "wf_plot")
    plot = widgets["wf_plot"]
    plot.show_toolbar(True)
    x_axis = w.XYPlotXAxis()
    x_axis.title("Time [s]")
    x_axis.auto_scale(True)
    x_axis.show_grid(True)
    y_axis = w.XYPlotYAxis()
    y_axis.title("Divisions")
    #y_axis.auto_scale(True)
    y_axis.minimum(-5.0)
    y_axis.maximum(5.0)
    y_axis.show_grid(True)

    trace1 = w.XYPlotTrace()
    trace1.name("CH1")
    trace1.x_pv(f"{prefix}tAxis")
    trace1.y_pv(f"{prefix}c01Waveform")

    trace2 = w.XYPlotTrace()
    trace2.name("CH2")
    trace2.x_pv(f"{prefix}tAxis")
    trace2.y_pv(f"{prefix}c02Waveform")

    trace3 = w.XYPlotTrace()
    trace3.name("CH3")
    trace3.x_pv(f"{prefix}tAxis")
    trace3.y_pv(f"{prefix}c03Waveform")

    trace4 = w.XYPlotTrace()
    trace4.name("CH4")
    trace4.x_pv(f"{prefix}tAxis")
    trace4.y_pv(f"{prefix}c04Waveform")

    plot.add_x_axis(x_axis)
    plot.add_y_axis(y_axis)
    plot.add_trace(trace1)
    plot.add_trace(trace2)
    plot.add_trace(trace3)
    plot.add_trace(trace4)

    screen.add_widget(list(widgets.values()))

    out = Path(__file__).with_name("simplescope.bob")
    screen.write_screen(str(out))

if __name__ == "__main__":
    main()
