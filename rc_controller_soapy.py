import tkinter as tk
import numpy as np
import SoapySDR

class RCController():

    _radio_center_frequency: int = 25e6
    _rc_control_frequency: int = 27e6
    _sample_rate: int = 8e6

    _after_delay_ms: int = 15

    _key_map = {
        "w":"n", "x":"s", "d":"e", "a":"w",
        "q":"nw", "e":"ne", "z":"sw", "c":"se",
    }

    def __init__(self):
        self.view = RCControllerView(self._button_press_handler, self._button_unpress_handler)
        self.view.bind("<Key>", lambda e: self._key_press_handler(e.char))
        self.view.bind("<KeyRelease>", lambda e: self._key_unpress_handler(e.char))
        
        self.generator = RCControllerSignalGenerator(self._sample_rate)

        # Setup radio params
        self.radio = SoapySDR.Device(dict(driver="hackrf"))
        self.radio.setSampleRate(SoapySDR.SOAPY_SDR_TX, 0, self._sample_rate)
        self.radio.setFrequency(SoapySDR.SOAPY_SDR_TX, 0, self._radio_center_frequency)
        self.radio.setGain(SoapySDR.SOAPY_SDR_TX, 0, "VGA", 47)
        self.radio.setGain(SoapySDR.SOAPY_SDR_TX, 0, "AMP", 16)

        # Setup transmit streams
        self.txStream = self.radio.setupStream(SoapySDR.SOAPY_SDR_TX, SoapySDR.SOAPY_SDR_CF32, [0])

        # Save away the STOP command for later
        cmd_stop = self.generator.generate_signal("x")
        self._stop_command = self._modulate_signal(np.array(cmd_stop))

    def start(self):
        """Main controller operation, callback functions called when buttons pressed"""
        self._set_current_command("o")
        self.radio.activateStream(self.txStream)
        self._job = self.view.after(self._after_delay_ms, self._transmit_current_command)

        self.view.mainloop()
        self.radio.deactivateStream(self.txStream)
        self.radio.closeStream(self.txStream)

    # Alternate driving
    def _key_press_handler(self, key):
        if key not in self._key_map.keys():
            return
        direction = self._key_map[key]
        self.view.after_cancel(self._job)
        self._set_current_command(direction)
        self._job = self.view.after(self._after_delay_ms, self._transmit_current_command)
    def _key_unpress_handler(self, *args):
        self._transmit_stop_command() 

    def _button_press_handler(self, direction):
        self.view.after_cancel(self._job)
        self._set_current_command(direction)
        self._job = self.view.after(self._after_delay_ms, self._transmit_current_command)

    def _button_unpress_handler(self, direction):
        self._transmit_stop_command()

    def _set_current_command(self, direction):
        cmd = self.generator.generate_signal(direction)
        mod_signal = self._modulate_signal(np.array(4*cmd))
        self._current_command = mod_signal
        
    def _transmit_stop_command(self):
        """Run our TX loop once for the STOP command"""
        self.view.after_cancel(self._job)
        self._transmit_command(self._stop_command)

        self._set_current_command("o")
        self._job = self.view.after(2, self._transmit_current_command)
    
    def _transmit_current_command(self):
        """Run our TX loop indefinitely with whatever command is running."""
        self._transmit_command(self._current_command)
        self._job = self.view.after(2, self._transmit_current_command)

    def _transmit_command(self, buffer):
        numSampsTotal = len(buffer)
        
        while numSampsTotal != 0:

            size = min(buffer.size, numSampsTotal)
            sr = self.radio.writeStream(self.txStream, [buffer], size)
            if not (sr.ret > 0): print("Fail %s, %d"%(sr, numSampsTotal))
            assert(sr.ret > 0)
            numSampsTotal -= sr.ret
            buffer = buffer[sr.ret:]

    def _modulate_signal(self, signal):
        frequency_offset = self._rc_control_frequency - self._radio_center_frequency
        t = np.arange(len(signal)) * 1/self._sample_rate
        mod_signal = np.array(signal) * np.exp(1j * 2 * np.pi * frequency_offset * t)
        return mod_signal.astype(np.complex64)


class RCControllerView(tk.Tk):
    _button_press_handler = None
    _button_unpress_handler = None

    def __init__(self, press_handler, unpress_handler):
        super().__init__()
        self.geometry("800x800")
        self._button_press_handler = press_handler
        self._button_unpress_handler = unpress_handler
        self._build_gui()


    def _build_gui(self):
        row0 = tk.Frame(self)
        row1 = tk.Frame(self)
        row2 = tk.Frame(self)

        # 8 buttons with 8 labels
        self.control_n = RCControllerButtonLight(row0, "N", self._button_press_handler, self._button_unpress_handler)
        self.control_e = RCControllerButtonLight(row1, "E", self._button_press_handler, self._button_unpress_handler)
        self.control_s = RCControllerButtonLight(row2, "S", self._button_press_handler, self._button_unpress_handler)
        self.control_w = RCControllerButtonLight(row1, "W", self._button_press_handler, self._button_unpress_handler)

        self.control_ne = RCControllerButtonLight(row0, "NE", self._button_press_handler, self._button_unpress_handler)
        self.control_se = RCControllerButtonLight(row2, "SE", self._button_press_handler, self._button_unpress_handler)
        self.control_nw = RCControllerButtonLight(row0, "NW", self._button_press_handler, self._button_unpress_handler)
        self.control_sw = RCControllerButtonLight(row2, "SW", self._button_press_handler, self._button_unpress_handler)

        self.control_nw.pack(expand=True, fill="both", side="left")
        self.control_n.pack(expand=True, fill="both", side="left")
        self.control_ne.pack(expand=True, fill="both", side="left")

        self.control_w.pack(expand=True, fill="both", side="left")
        self.control_e.pack(expand=True, fill="both", side="left")

        self.control_sw.pack(expand=True, fill="both", side="left")
        self.control_s.pack(expand=True, fill="both", side="left")
        self.control_se.pack(expand=True, fill="both", side="left")

        row0.pack(expand=True, fill="both", side="top")
        row1.pack(expand=True, fill="both", side="top")
        row2.pack(expand=True, fill="both", side="top")

class RCControllerButtonLight(tk.Frame):
    _button_press_handler = None
    _button_unpress_handler = None
    _key_bindings = {
        "N": "w", "n": "w",
        "S": "x", "s": "x",
        "E": "d", "e": "d",
        "W": "a", "w": "a",
        "NE": "e", "ne": "e",
        "SE": "c", "se": "c",
        "NW": "q", "nw": "q",
        "SW": "z", "sw": "z",
    }
    def __init__(self, master, direction, press_handler, unpress_handler):
        super().__init__(master)
        self.indicator = tk.Label(self, bg="red")
        self.button = tk.Button(self, text=direction)
        self.direction = direction
        self.indicator.pack(expand=True, fill="both", side="top")
        self.button.pack(expand=True, fill="both", side="top")

        self.button_press_handler = press_handler
        self.button_unpress_handler = unpress_handler

    @property
    def button_press_handler(self):
        return self._button_press_handler
    
    @button_press_handler.setter
    def button_press_handler(self, handler):
        self._button_press_handler = handler
        click_event = "<1>"
        self.button.bind(click_event, lambda x: self.button_press_handler(self.direction))
        self.button.bind(click_event, lambda x: self.light_control(True), add="+")

    @property
    def button_unpress_handler(self):
        return self._button_unpress_handler
    
    @button_unpress_handler.setter
    def button_unpress_handler(self, handler):
        self._button_unpress_handler = handler
        click_event = "<ButtonRelease-1>"
        self.button.bind(click_event, lambda x: self.button_unpress_handler(self.direction))
        self.button.bind(click_event, lambda x: self.light_control(False), add="+")

    def light_control(self, on: bool):
        if on: self.indicator.configure(bg="green")
        else: self.indicator.configure(bg="red")

class RCControllerSignalGenerator():
    _clock_period = 0.0005 #0.5ms period for the On/Off keying commands

    def __init__(self, sample_rate):
        self._sample_rate = sample_rate

    def generate_signal(self, command:str):
        """
        Generates appropriate R/C control signals using cardinal directions (e.g., n is go forward, e is turn right)
        ...

        Attributes
        ----------
        command : str
            cardinal direction to drive the R/C car e.g, n=forward, ne=forward+right, s=reverse, x=stop, etc.
        """
        assert type(command) is str, "command must be a string (n,s,e,w,x) and combinations of them, x for STOP"
        low = [0] * int(self._sample_rate * self._clock_period)
        high = [0.95] * int(self._sample_rate * self._clock_period)

        long = 3 * high + low
        short = high + low
        cmd_forward         = 4 * long + 40 * short
        cmd_forward_right   = 4 * long + 46 * short
        cmd_forward_left    = 4 * long + 52 * short
        cmd_reverse         = 4 * long + 10 * short
        cmd_reverse_right   = 4 * long + 34 * short
        cmd_reverse_left    = 4 * long + 28 * short
        cmd_left            = 4 * long + 58 * short
        cmd_right           = 4 * long + 64 * short

        cmd_stop            = 15 * (4 * long + 4 * short)
        cmd_off             = 10 * low

        if "n" in command or "N" in command:
            if "e" in command or "E" in command:
                return cmd_forward_right
            if "w" in command or "W" in command:
                return cmd_forward_left
            return cmd_forward
        
        if "s" in command or "S" in command:
            if "e" in command or "E" in command:
                return cmd_reverse_right
            if "w" in command or "W" in command:
                return cmd_reverse_left
            return cmd_reverse
        if "e" in command or "E" in command:
            return cmd_right
        if "w" in command or "W" in command:
            return cmd_left
        if "x" in command or "X" in command:
            return cmd_stop
        
        if "o" in command or "O" in command:
            return cmd_off

if __name__ == "__main__":
    
    rc = RCController()
    rc.start()