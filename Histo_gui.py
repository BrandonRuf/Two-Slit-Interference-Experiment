import spinmob.egg   as _egg
import spinmob       as _s
import os            as _os
import serial        as _serial

import time     as _time
import shutil   as _shutil
import numpy    as _n
import scipy.special as _scipy_special
import sys as _sys

import traceback as _traceback
_p = _traceback.print_last
_d = _s.data

# import pyqtgraph and create the App.
import pyqtgraph as _pg
from spinmob.egg._gui import Button, ComboBox, NumberBox, Label, TextBox
_g = _egg.gui

from serial.tools.list_ports import comports as _comports
from PCIT1_api    import PCIT1_api

# GUI settings
_s.settings['dark_theme_qt'] = True

# Defined fonts
style_1 = 'font-size: 14pt; font-weight: bold; color: '+('mediumspringgreen' if _s.settings['dark_theme_qt'] else 'blue')
style_2 = 'font-size: 17pt; font-weight: bold; color: '+('white'             if _s.settings['dark_theme_qt'] else 'red')
style_3 = 'font-size: 17pt; font-weight: bold; color: '+('cyan'              if _s.settings['dark_theme_qt'] else 'purple')

# 
PROGRAM_STEPS = 10
PROGRAM_DIR   = 'Programs'


class serial_gui_base(_g.BaseObject):
    """
    Base class for creating a serial connection gui. Handles common controls.
    
    Parameters
    ----------
    api_class=None : class
        Class to use when connecting. For example, api_class=PCIT1_api would
        work. Note this is not an instance, but the class itself. An instance is
        created when you connect and stored in self.api.
        
    name='serial_gui' : str
        Unique name to give this instance, so that its settings will not
        collide with other egg objects.
        
    show=True : bool
        Whether to show the window after creating.
        
    block=False : bool
        Whether to block the console when showing the window.
        
    window_size=[1,1] : list
        Dimensions of the window.
    hide_address=False: bool
        Whether to show the address control for things like the Auber.
    """
    def __init__(self, api_class = PCIT1_api, name='serial_gui', show=True, block=False, window_size=[1,1], hide_address=False):

        # Remebmer the name.
        self.name = name

        # Checks periodically for the last exception
        self.timer_exceptions = _g.TimerExceptions()
        self.timer_exceptions.signal_new_exception.connect(self._new_exception)

        # Where the actual api will live after we connect.
        self.api = None
        self._api_class = api_class

        # GUI stuff
        self.window   = _g.Window(
            self.name, size=window_size, autosettings_path=name+'.window',
            event_close = self._window_close)
        
        # Top of GUI (Serial Communications)
        self.grid_top = self.window.place_object(_g.GridLayout(margins=False), alignment=0)
        self.window.new_autorow()

        # Get all the available ports
        self._label_port = self.grid_top.add(_g.Label('Port:'))
        self._ports = [] # Actual port names for connecting
        ports       = [] # Pretty port names for combo box
        if _comports:
            for p in _comports():
                self._ports.append(p.device)
                ports      .append(p.description)
        
        # Append simulation port
        ports      .append('Simulation')
        self._ports.append('Simulation')
        
        # Append refresh port
        ports      .append('Refresh - Update Ports List')
        self._ports.append('Refresh - Update Ports List')
        
        self.combo_ports = self.grid_top.add(_g.ComboBox(ports, autosettings_path=name+'.combo_ports'))
        self.combo_ports.signal_changed.connect(self._ports_changed)

        self.grid_top.add(_g.Label('Address:')).show(hide_address)
        self.number_address = self.grid_top.add(_g.NumberBox(
            0, 1, int=True,
            autosettings_path=name+'.number_address',
            tip='Address (not used for every instrument)')).set_width(40).show(hide_address)

        self.grid_top.add(_g.Label('Baud:'))
        self.combo_baudrates = self.grid_top.add(_g.ComboBox(
            ['9600','57600', '115200','230400'],
            default_index=3,
            autosettings_path=name+'.combo_baudrates'))

        self.grid_top.add(_g.Label('Timeout:'))
        self.number_timeout = self.grid_top.add(_g.NumberBox(15, dec=True, bounds=(1, None), suffix='s', tip='How long to wait for an answer before giving up (ms).', autosettings_path=name+'.number_timeout')).set_width(100)

        # Button to connect
        self.button_connect  = self.grid_top.add(_g.Button('Connect', checkable=True))

        # Stretch remaining space
        self.grid_top.set_column_stretch(self.grid_top._auto_column)

        # Connect signals
        self.button_connect.signal_toggled.connect(self._button_connect_toggled)
        
        # Status
        self.label_status = self.grid_top.add(_g.Label(''))

        # Expand the bottom grid
        self.window.set_row_stretch(1)
        
        # Error
        self.grid_top.new_autorow()
        self.label_message = self.grid_top.add(_g.Label(''), column_span=10).set_colors('pink' if _s.settings['dark_theme_qt'] else 'red')

        # Other data
        self.t0 = None

        # Run the base object stuff and autoload settings
        _g.BaseObject.__init__(self, autosettings_path=name)

        # Show the window.
        if show: self.window.show(block)
    
    def _ports_changed(self):
        """
        Refreshes the list of availible serial ports in the GUI.

        """
        if self.get_selected_port() == 'Refresh - Update Ports List':
            
            len_ports = len(self.combo_ports.get_all_items())
            
            # Clear existing ports
            if(len_ports > 1): # Stop recursion!
                for n in range(len_ports):
                    self.combo_ports.remove_item(0)
            else:
                return
                self.combo_ports.remove_item(0)
                 
            self._ports = [] # Actual port names for connecting
            ports       = [] # Pretty port names for combo box
                
            default_port = 0
             
            # Get all the available ports
            if _comports:
                for inx, p in enumerate(_comports()):
                    self._ports.append(p.device)
                    ports      .append(p.description)
                    
                    if 'Arduino' in p.description:
                        default_port = inx
                        
            # Append simulation port
            ports      .append('Simulation')
            self._ports.append('Simulation')
            
            # Append refresh port
            ports      .append('Refresh - Update Ports List')
            self._ports.append('Refresh - Update Ports List')
             
            # Add the new list of ports
            for item in ports:
                self.combo_ports.add_item(item)
             
            # Set the new default port
            self.combo_ports.set_index(default_port)
    
    def _button_connect_toggled(self, *a):
        """
        Connect by creating the API.
        """
        if self._api_class is None:
            raise Exception('You need to specify an api_class when creating a serial GUI object.')

        # If we checked it, open the connection and start the timer.
        if self.button_connect.is_checked():
            port = self.get_selected_port()
            self.api = self._api_class(
                    port=port,
                    baudrate=int(self.combo_baudrates.get_text()),
                    timeout=self.number_timeout.get_value())

            # Record the time if it's not already there.
            if self.t0 is None: self.t0 = _time.time()

            # Enable the grid
            self.grid_bot.enable()

            # Disable serial controls
            self.combo_baudrates.disable()
            self.combo_ports    .disable()
            self.number_timeout .disable()
            
            
            if self.api.simulation_mode:
                #self.label_status.set_text('*** Simulation Mode ***')
                #self.label_status.set_colors('pink' if _s.settings['dark_theme_qt'] else 'red')
                self.combo_ports.set_value(len(self._ports)-2)
                self.button_connect.set_text("Simulation").set_colors(background='pink')
            else:
                self.button_connect.set_text('Disconnect').set_colors(background = 'blue')

        # Otherwise, shut it down
        else:
            self.api.disconnect()
            #self.label_status.set_text('')
            self.button_connect.set_colors()
            self.grid_bot.disable()

            # Enable serial controls
            self.combo_baudrates.enable()
            self.combo_ports    .enable()
            self.number_timeout .enable()
            
            self.button_connect.set_text('Connect').set_colors(background = '')


        # User function
        self._after_button_connect_toggled()

    def _after_button_connect_toggled(self):
        """
        Dummy function called after connecting.
        """
        return

    def _new_exception(self, a):
        """
        Just updates the status with the exception.
        """
        self.label_message(str(a)).set_colors('red')

    def _window_close(self):
        """
        Disconnects. When you close the window.
        """
        print('Window closed but not destroyed. Use show() to bring it back.')
        if self.button_connect():
            print('  Disconnecting...')
            self.button_connect(False)

    def get_selected_port(self):
        """
        Returns the actual port string from the combo box.
        """
        return self._ports[self.combo_ports.get_index()]
    
    def get_com_ports():
        """
        Returns a dictionary of port names as keys and descriptive names as values.
        """
        if _comports:
    
            ports = dict()
            for p in _comports(): ports[p.device] = p.description
            return ports
    
        else:
            raise Exception('You need to install pyserial and have Windows to use get_com_ports().')
            
    def list_com_ports():
        """
        Prints a "nice" list of available COM ports.
        """
        ports = get_com_ports()
    
        # Empty dictionary is skipped.
        if ports:
            keys = list(ports.keys())
            keys.sort()
            print('Available Ports:')
            for key in keys:
                print(' ', key, ':', ports[key])
    
        else: raise Exception('No ports available. :(')
        
        

class histo(serial_gui_base):

    def __init__(self, name='PCIT1-A', api = PCIT1_api, show=True, block=False, window_size=[1,300]):


        # Run the base class stuff, which shows the window at the end.
        serial_gui_base.__init__(self, api_class=api, name=name, show=False, window_size=window_size)
        
        self.window.set_size([0,0])

        # Build the GUI
        self.gui_components(name)
        
        # Finally show it.
        self.window.show(block)
     

        
    def _after_button_connect_toggled(self):
        """
        Called after the connection or disconnection routine.
        """
        if self.button_connect.is_checked():
    
            # Get the setpoint
            try:
                self.timer.start()
                
                
            except:
                self.button_connect.set_checked(False)
        
        # Disconnected
        else:
            self.timer.stop()
    
    
    def _timer_tick(self, *a):
        """
        Called whenever the timer ticks. Let's update the plot and save the latest data.
        """
        current_time = _time.time()
        
        # Get the time, temperature, and setpoint
        t = current_time - self.t0
        N, C = self.api.read_all_data()  
        
        for i in range(len(C)):
            # Append this to the databox
            self.plot.append_row([t, C[i]], ckeys=['Time (s)', 'Counts (C)'])
        self.plot.plot()

        # Update the GUI
        self.window.process_events()
    
    def gui_components(self,name):
        self.grid_bot = self.window.place_object(_g.GridLayout(margins=False), alignment=0)
       
        # Add data plotting to main tab
        self.plot = self.grid_bot.add(DataboxPlot(
            file_type='*.csv',
            autosettings_path=name+'.plot',
            delimiter=',', styles = [dict(pen=(0,1)), dict(pen=None, symbol='o')], alignment=0, column_span=10))
        
        # Timer for collecting data
        self.timer = _g.Timer(interval_ms=1000, single_shot=False)
        self.timer.signal_tick.connect(self._timer_tick)

        
        
class DataboxPlot(_d.databox, _g.GridLayout):
    """
    This object is a spinmob databox plus a collection of common controls and
    functionality for plotting, saving, loading, and manipulating data on the
    fly.
    ROIs for each plot can be stored in self.ROIs as a list (sub-lists allowed)
    Parameters
    ----------
    file_type="*.dat"
        What type of file to use for dialogs and saving.
    autosettings_path=None
        autosettings_path=None means do not automatically save the configuration
        of buttons / controls / script etc. Setting this to a path will cause
        DataboxPlot to automatically save / load the settings. Note you will
        need to specify a different path for each DataboxPlot instance.
    autoscript=1
        Sets the default autoscript entry in the combobox. Set to 0 for the
        manual script, and 4 for the custom autoscript, which can be
        defined by overwriting the function self.autoscript_custom, which
        needs only return a valid script string.
    name=None
        Stored in self.name for your purposes.
    styles=[]
        Optional list of dictionaries defining the styles, one for each plotted
        data set. Stored as self._styles (which you can later set again), each
        dictionary is used to send keyword arguments as PlotDataItem(**styles[n])
        for the n'th data set. Note these are the same keyword arguments one
        can supply to pyqtgraph's plot() function. See pyqtgraph examples, e.g.,
        import pyqtgraph.examples; pyqtgraph.examples.run()
        or http://www.pyqtgraph.org/documentation/plotting.html
        Typical example: styles = [dict(pen=(0,1)), dict(pen=None, symbol='o')]
    **kwargs are sent to the underlying databox
    Note checking the "Auto-Save" button does not result in the data being automatically
    saved until you explicitly call self.autosave() (which does nothing
    unless auto-saving is enabled).
    About Plot Scripts
    ------------------
    Between the top controls and the plot region is a text box in which you can
    define an arbitrary python plot script (push the "Script" button to toggle
    its visibility). The job of this script is minimally to define x and y.
    These can both be arrays of data or lists of arrays of data to plot. You may
    also specify None for one of them. You can also similarly (optionally)
    define error bars with ey, xlabels, ylabels, and styles. Once you have
    stored some columns of data in this object, try selecting the different
    options in the combo box to see example / common scripts, or select "Edit"
    to create your own.
    The script's namespace includes: all of numpy (sin, cos, sqrt, array, etc),
    all of scipy.special (erf, erfc, etc), d=self, styles=self._styles,
    sm=s=_s=spinmob, and everything in self.plot_script_globals.
    Optional additional globals can be defined by setting
    self.plot_script_globals to a dictionary of your choice. For example,
    self.plot_script_globals = dict(d2=self.my_other_databox) will expose
    self.my_other_databox to the script as d2.
    The script is executed by either self.plot() or when you click the
    "Try it!" button. If there is an error, the script will turn pink and the
    error will be printed to the console, but this is a "safe" crash and will
    not affect the flow of the program otherwise.
    Importantly, this script will NOT affect the underlying data unless you
    use it to actually modify the variable d, e.g., d[0] = d[0]+3.
    """

    def __init__(self, file_type="*.dat", autosettings_path=None, autoscript=1,
                 name=None, show_logger=False, styles=[], **kwargs):

        self.name = name

        # Do all the parent class initialization; this sets _widget and _layout
        _g.GridLayout.__init__(self, margins=False)
        _d.databox.__init__(self, **kwargs)
        self._alignment_default = 0 # By default, fill all space.

        # top row is main controls
        self.grid_controls   = self.place_object(_g.GridLayout(margins=False), alignment=0)
        self.grid_controls.event_resize = self._event_resize_databox_plot

        self.grid_controls1  = self.grid_controls.place_object(_g.GridLayout(margins=False), 0,0, alignment=1)

        self.button_clear    = self.grid_controls1.place_object(Button("Clear", tip='Clear all header and columns.').set_width(40), alignment=1)
        self.button_load     = self.grid_controls1.place_object(Button("Load",  tip='Load data from file.')         .set_width(40), alignment=1)
        self.button_save     = self.grid_controls1.place_object(Button("Save",  tip='Save data to file.')           .set_width(40), alignment=1)
        self.combo_binary    = self.grid_controls1.place_object(ComboBox(['Text', 'float16', 'float32', 'float64', 'int8', 'int16', 'int32', 'int64', 'complex64', 'complex128', 'complex256'], tip='Format of output file columns.'), alignment=1)
        self.button_autosave = self.grid_controls1.place_object(Button("Auto",   checkable=True, tip='Enable autosaving. Note this will only autosave when self.autosave() is called in the host program.').set_width(40), alignment=1)
        self.number_file     = self.grid_controls1.place_object(NumberBox(int=True, bounds=(0,None), tip='Current autosave file name prefix number. This will increment every autosave().'))

        self.label_path      = self.grid_controls.place_object(Label(""), 1,0)

        self.grid_controls2 = self.grid_controls.place_object(_g.GridLayout(margins=False), 0,1, alignment=1)
        self.grid_controls.set_column_stretch(2)

        self.button_script     = self.grid_controls2.place_object(Button  ("Script",      checkable=True, checked=True, tip='Show the script box.').set_width(50)).set_checked(False)
        self.combo_autoscript  = self.grid_controls2.place_object(ComboBox(['Edit', 'x=d[0]', 'Pairs', 'Triples', 'x=d[0], ey', 'x=None', 'User'], tip='Script mode. Select "Edit" to modify the script.')).set_value(autoscript)
        self.button_multi      = self.grid_controls2.place_object(Button  ("Multi",       checkable=True, tip="If checked, plot with multiple plots. If unchecked, all data on the same plot.").set_width(40)).set_checked(True)
        self.button_link_x     = self.grid_controls2.place_object(Button  ("Link",        checkable=True, tip="Link the x-axes of all plots.").set_width(40)).set_checked(autoscript==1)
        self.button_enabled    = self.grid_controls2.place_object(Button  ("Enable",      checkable=True, tip="Enable this plot.").set_width(50)).set_checked(True)

        # second rows is the script
        self.new_autorow()

        # grid for the script
        self.grid_script = self.place_object(_g.GridLayout(margins=False), 0,1, alignment=0)

        # script grid
        self.button_save_script = self.grid_script.place_object(Button("Save", tip='Save the shown script.').set_width(40), 2,1)
        self.button_load_script = self.grid_script.place_object(Button("Load", tip='Load a script.').set_width(40), 2,2)
        self.button_plot        = self.grid_script.place_object(Button("Plot!", tip='Attempt to plot using the shown script!').set_width(40), 2,3)

        self.script = self.grid_script.place_object(TextBox("", multiline=True,
            tip='Script defining how the data is plotted. The minimum requirement is that\n'+
                'x and y (arrays, lists of arrays, or None) are defined. Optionally, you may\n'+
                'also define:\n\n'+

                '  ey : number, array or list of numbers and/or arrays\n    defines y-error bars for each data set\n\n'+

                '  xlabels, ylabels : string or list of strings\n    defines axis labels for each data set.\n\n'+

                '  styles : list of dictionaries and/or or None\'s (default)\n    Keword arguments to be sent to pyqtgraph.PlotDataItem() when\n    creating the curves.\n\n'+

                'The script knows about all numpy objects (sin, cos, sqrt, array, etc),\n'+
                'scipy.special functions (also via special.), and self.plot_script_globals,\n'+
                '(dictionary) which allows you to include your own variables and objects.\n'+
                'Finally, the following variables are defined by default:\n\n'+

                '  mkPen & mkBrush : from pyqtgraph, used for creating styles.\n\n'+

                '  d : this DataboxPlot instance\n\n' +

                '  spinmob, sm, s, and _s : spinmob library'),
                1,0, row_span=4, alignment=0)
        self.script.set_height(120)

            # g = dict(_n.__dict__, np=_n, _n=_n, numpy=_n)
            # g.update(_scipy_special.__dict__, special=_scipy_special)
            # g.update(dict(mkPen=_pg.mkPen, mkBrush=_pg.mkBrush))
            # g.update(dict(d=self, x=None, y=None, ex=None, ey=None, styles=self._styles))
            # g.update(dict(xlabels='x', ylabels='y'))
            # g.update(dict(spinmob=_s, sm=_s, s=_s, _s=_s))
            # g.update(self.plot_script_globals)

        #self.script.set_style('font-family:monospace; font-size:12;')
        # Windows compatibility
        font = _s._qtw.QFont()
        font.setFamily("monospace")
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.script._widget.setFont(font)

        self._label_script_error = self.place_object(Label('ERRORS GO HERE'), 0,2, column_span=2, alignment=0)
        self._label_script_error.hide()


        # make sure the plot fills up the most space
        self.set_row_stretch(3)

        # plot area
        self.grid_plot = self.place_object(_g.GridLayout(margins=False), 0,3, column_span=self.get_column_count(), alignment=0)

        # History area
        self.grid_logger = self.add(_g.GridLayout(margins=False), 0,4, column_span=self.get_column_count(), alignment=0)

        self.grid_logger.add(Label('History:'), alignment=0)
        self.grid_logger.set_column_stretch(2)
        self.number_history = self.grid_logger.add(NumberBox(
            0, step=100, bounds=(0,None), int=True,
            tip='How many points to keep in the plot when using append_row(). Set to 0 to keep everything.\n'+
                'You can also use the script to display the last N points with indexing,\n'+
                'e.g., d[0][-200:], which will not delete the old data.')).set_width(70)

        self.text_log_note = self.grid_logger.add(TextBox(
            'Note', tip='Note to be added to the header when saving.'), alignment=0)

        self.button_log_data = self.grid_logger.add(Button(
            'Log Data',
            checkable=True,
            signal_toggled=self._button_log_data_toggled,
            tip='Append incoming data to a text file of your choice when calling self.append_row(). Saves the current data and header first.'
            )).set_width(70).set_colors_checked('white', 'red')

        self.label_log_path = self.grid_logger.add(Label('')).hide()
        if not show_logger: self.grid_logger.hide()



        ##### set up the internal variables

        # will be set later. This is where files will be dumped to when autosaving
        self._autosave_directory = None

        # file type (e.g. *.dat) for the file dialogs
        self.file_type = file_type

        # autosave settings path
        self._autosettings_path = autosettings_path

        # holds the curves and plot widgets for the data, and the buttons
        self._curves          = []
        self._errors          = []
        self._legend          = None
        self._styles          = []   # List of dictionaries to send to PlotDataItem's
        self._previous_styles = None # Used to determine if a rebuild is necessary
        self.plot_widgets     = []
        self.ROIs             = []

        ##### Functionality of buttons etc...

        self.button_plot       .signal_clicked.connect(self._button_plot_clicked)
        self.button_save       .signal_clicked.connect(self._button_save_clicked)
        self.button_save_script.signal_clicked.connect(self._button_save_script_clicked)
        self.button_load       .signal_clicked.connect(self._button_load_clicked)
        self.button_load_script.signal_clicked.connect(self._button_load_script_clicked)
        self.button_clear      .signal_clicked.connect(self._button_clear_clicked)
        self.button_autosave   .signal_toggled.connect(self._button_autosave_clicked)
        self.button_script     .signal_toggled.connect(self._button_script_clicked)
        self.combo_binary      .signal_changed.connect(self._combo_binary_changed)
        self.combo_autoscript  .signal_changed.connect(self._combo_autoscript_clicked)
        self.button_multi      .signal_toggled.connect(self._button_multi_clicked)
        self.button_link_x     .signal_toggled.connect(self._button_link_x_clicked)
        self.button_enabled    .signal_toggled.connect(self._button_enabled_clicked)
        self.number_file       .signal_changed.connect(self._number_file_changed)
        self.script            .signal_changed.connect(self._script_changed)
        self.number_history    .signal_changed.connect(self.save_gui_settings)
        self.text_log_note     .signal_changed.connect(self.save_gui_settings)

        # list of controls we should auto-save / load
        self._autosettings_controls = ["self.combo_binary",
                                       "self.combo_autoscript",
                                       "self.button_enabled",
                                       "self.button_multi",
                                       "self.button_link_x",
                                       "self.button_script",
                                       "self.number_file",
                                       "self.script",
                                       "self.number_history",
                                       "self.text_log_note", ]

        # load settings if a settings file exists and initialize
        self.load_gui_settings()
        self._synchronize_controls()

    def _event_resize_databox_plot(self):
        """
        Called when the widget resizes.
        """
        # If we're below a certain width, move the right controls below
        # if self.grid_controls._widget.width() < 700: self.grid_controls.place_object(self.grid_controls2, 0,1, alignment=1)
        # else:                                        self.grid_controls.place_object(self.grid_controls2, 2,0, alignment=2)

    def _button_log_data_toggled(self, *a):
        """
        Called when someone toggles the dump button. Ask for a path or remove the path.
        """
        if self.button_log_data.is_checked():
            path = _s.dialogs.save(self.file_type, 'Dump incoming data to this file.', force_extension=self.file_type)

            # If the path is valid, reset the clock, write the header
            if path:

                # Store the path in a visible location
                self.label_log_path.set_text(path).show()
                self.text_log_note.disable()

                # Add header information to the Databox
                self.h(**{
                    'DataboxPlot_Note'              : self.text_log_note(),
                    'DataboxPlot_LogFileCreated'    : _t.ctime(_t.time()),
                    'DataboxPlot_LogFileCreated(s)' : _t.time(),})

                if len(self.ckeys): self.h(**{'Log File Initial Row Count' : len(self[0])})
                else:               self.h(**{'Log File Initial Row Count' : 0})

                # Save it forcing overwrite
                self.save_file(path, force_overwrite=True)

            else:
                self.button_log_data.set_checked(False)
                self.text_log_note.enable()

        else:
            self.label_log_path.set_text('').hide()
            self.text_log_note.enable()

    def __repr__(self): return "<DataboxPlot instance: " + self._repr_tail()

    def _button_enabled_clicked(self, *a):  self.save_gui_settings()
    def _number_file_changed(self, *a):     self.save_gui_settings()
    def _script_changed(self, *a):          self.save_gui_settings()

    def _button_save_script_clicked(self, *a):
        """
        When someone wants to save their script.
        """
        path = _s.dialogs.save('*.py', text='Save script to...', force_extension='*.py', default_directory='DataboxPlot_scripts')
        if not path: return

        f = open(path, 'w')
        f.write(self.script.get_text())
        f.close()

    def _button_load_script_clicked(self, *a):
        """
        When someone wants to load their script.
        """
        path = _s.dialogs.load('*.py', default_directory='DataboxPlot_scripts')
        if not path: return

        self.load_script(path)

    def load_script(self, path=None):
        """
        Loads a script at the specified path.
        Parameters
        ----------
        path=None
            String path of script file. Setting this to None will bring up a
            load dialog.
        """
        if path == None: self._button_load_script_clicked()
        else:
            f = open(path, 'r')
            s = f.read()
            f.close()

            self.script.set_text(s)
            self.combo_autoscript.set_value(0)

    def _button_multi_clicked(self, *a):
        """
        Called whenever someone clicks the Multi button.
        """
        self.plot()
        self.save_gui_settings()

    def _button_link_x_clicked(self, *a):
        """
        Called whenever the Link X button is clicked.
        """
        self._update_linked_axes()
        self.save_gui_settings()

    def _combo_autoscript_clicked(self, *a):
        """
        Called whenever the combo is clicked.
        """
        self._synchronize_controls()
        self.plot()
        self.save_gui_settings()

    def _combo_binary_changed(self, *a):
        """
        Called whenever the combo is clicked.
        """
        self.save_gui_settings()

    def _button_script_clicked(self, checked):
        """
        Called whenever the button is clicked.
        """
        self._synchronize_controls()
        self.save_gui_settings()

    def _button_autosave_clicked(self, checked):
        """
        Called whenever the button is clicked.
        """
        if checked:
            # get the path from the user
            path = _s.dialogs.save(filters=self.file_type, force_extension=self.file_type)

            # abort if necessary
            if not path:
                self.button_autosave.set_checked(False)
                return

            # otherwise, save the info!
            self._autosave_directory, filename = _os.path.split(path)
            self.label_path.set_text(filename)

        self.save_gui_settings()

    def _button_save_clicked(self, *a):
        """
        Called whenever the button is clicked.
        """
        self.save_file()

    def _button_load_clicked(self, *a):
        """
        Called whenever the button is clicked.
        """
        self.load_file()

    def _button_clear_clicked(self, *a):
        """
        Called whenever the button is clicked.
        """
        self.clear()
        self.plot()

        self.after_clear()

    def after_clear(self):
        """
        Dummy function you can overwrite to run code after the clear button
        is done.
        """
        return

    def before_save_file(self):
        """
        Called at the start of save_file(). You can overload this to insert
        your own functionality.
        """
        return

    def append_row(self, row, ckeys=None, history=True):
        """
        Appends the supplied row of data, using databox.append_row(), but with
        history equal to the current value in self.number_history. Also, if the
        "Log Data" button is enabled, appends the new data to the log file.
        Parameters
        ----------
        row : list or 1D array
            Values for the new row of data.
        ckeys=None : list of strings (optional)
            Column keys the databox must enforce. If they don't match the current
            keys, the columns will be cleared and the new ckeys will be used.
        history=True : True or integer
            Number of previous data points to keep in memory. If True (default),
            use self.number_history's value. If 0, kep all data.
        """
        if history is True: history = self.number_history()

        # First append like normal
        super().append_row(row, ckeys, history)

        # If the dump file is checked, dump the row
        if self.button_log_data() and len(self.label_log_path()):

            # Get a list of strings
            row_strings = []
            for x in row: row_strings.append(str(x))

            # The most pythony python that ever pythoned.
            delimiter = '\t' if self.delimiter is None else self.delimiter

            # Append a single line.
            f = open(self.label_log_path(), 'a')
            f.write(delimiter.join(row_strings)+'\n')
            f.close()

        return self

    def save_file(self, path=None, force_overwrite=False, just_settings=False, **kwargs):
        """
        Saves the data in the databox to a file.
        Parameters
        ----------
        path=None
            Path for output. If set to None, use a save dialog.
        force_overwrite=False
            Do not question the overwrite if the file already exists.
        just_settings=False
            Set to True to save only the state of the DataboxPlot controls
            Note that setting header_only=True will include settings and the usual
            databox header.
        **kwargs are sent to the normal databox save_file() function.
        """
        self.before_save_file()

        # Update the log file note
        self.h(**{'DataboxPlot_Note' : self.text_log_note(),})

        # Update the binary mode
        if not 'binary' in kwargs: kwargs['binary'] = self.combo_binary.get_text()

        # if it's just the settings file, make a new databox with no columns
        if just_settings: d = _d.databox()

        # otherwise use the internal databox with the columns
        else: d = self

        # add all the controls settings to the header
        for x in self._autosettings_controls: self._store_gui_setting(d, x)

        # save the file using the skeleton function, so as not to recursively
        # call this one again!
        _d.databox.save_file(d, path, self.file_type, self.file_type, force_overwrite, **kwargs)

        return self

    def load_file(self, path=None, just_settings=False, just_data=False):
        """
        Loads a data file. After the file is loaded, calls self.after_load_file(self),
        which you can overwrite if you like!
        Parameters
        ----------
        path=None
            Optional path. If not specified, pops up a dialog.
        just_settings=False
            Load only the settings, not the data
        just_data=False
            Load only the data, not the settings.
        Returns
        -------
        self
        """
        # if it's just the settings file, make a new databox
        if just_settings:
            d = _d.databox()
            header_only = True

        # otherwise use the internal databox
        else:
            d = self
            header_only = False

        # Load the file
        result = _d.databox.load_file(d, path, filters=self.file_type, header_only=header_only, quiet=just_settings)

        # import the settings if they exist in the header
        if not just_data:

            if not None == result:

                # loop over the autosettings and update the gui
                for x in self._autosettings_controls: self._load_gui_setting(x,d)

            # always sync the internal data
            self._synchronize_controls()

        # plot the data if this isn't just a settings load
        if not just_settings:
            self.plot()
            self.after_load_file()


    def after_load_file(self,*args):
        """
        Called after a file is loaded. Does nothing. Feel free to overwrite!
        The first argument is the DataboxPlotInstance so your function can
        tell which instance loaded a file.
        """
        return

    def _button_plot_clicked(self, *a):
        """
        Called whenever the button is pressed.
        """
        self.plot()

    def _generate_autoscript(self):
        """
        Automatically generates a python script for plotting.
        """
        # This should never happen unless I screwed up.
        if self.combo_autoscript.get_index() == 0: return "ERROR: Ask Jack."

        # if there is no data, leave it blank
        if   len(self)==0: return "x = []; y = []; xlabels=[]; ylabels=[]"

        # if there is one column, make up a one-column script
        elif len(self)==1: return "x = [None]\ny = [ d[0] ]\n\nxlabels=[ 'Data Point' ]\nylabels=[ 'd[0]' ]"

        # Shared x-axis (column 0)
        elif self.combo_autoscript.get_index() == 1:

            # hard code the first columns
            sx = "x = ( d[0]"
            sy = "y = ( d[1]"

            # hard code the first labels
            sxlabels = "xlabels = '" +self.ckeys[0]+"'"
            sylabels = "ylabels = ( '"+self.ckeys[1]+"'"

            # loop over any remaining columns and append.
            for n in range(2,len(self)):
                sy += ", d["+str(n)+"]"
                sylabels += ", '"+self.ckeys[n]+"'"

            return sx+" )\n"+sy+" )\n\n"+sxlabels+"\n"+sylabels+" )\n"


        # Column pairs
        elif self.combo_autoscript.get_index() == 2:

            # hard code the first columns
            sx = "x = ( d[0]"
            sy = "y = ( d[1]"

            # hard code the first labels
            sxlabels = "xlabels = ( '"+self.ckeys[0]+"'"
            sylabels = "ylabels = ( '"+self.ckeys[1]+"'"

            # Loop over the remaining columns and append
            for n in range(1,int(len(self)/2)):
                sx += ", d["+str(2*n  )+"]"
                sy += ", d["+str(2*n+1)+"]"
                sxlabels += ", '"+self.ckeys[2*n  ]+"'"
                sylabels += ", '"+self.ckeys[2*n+1]+"'"

            return sx+" )\n"+sy+" )\n\n"+sxlabels+" )\n"+sylabels+" )\n"

        # Column triples
        elif self.combo_autoscript.get_index() == 3:

            # hard code the first columns
            sx = "x = ( d[0], d[0]"
            sy = "y = ( d[1], d[2]"

            # hard code the first labels
            sxlabels = "xlabels = ( '"+self.ckeys[0]+"', '"+self.ckeys[0]+"'"
            sylabels = "ylabels = ( '"+self.ckeys[1]+"', '"+self.ckeys[2]+"'"

            # Loop over the remaining columns and append
            for n in range(1,int(len(self)/3)):
                sx += ", d["+str(3*n  )+"], d["+str(3*n  )+"]"
                sy += ", d["+str(3*n+1)+"], d["+str(3*n+2)+"]"

                sxlabels += ", '"+self.ckeys[3*n  ]+"', '"+self.ckeys[3*n  ]+"'"
                sylabels += ", '"+self.ckeys[3*n+1]+"', '"+self.ckeys[3*n+2]+"'"

            return sx+" )\n"+sy+" )\n\n"+sxlabels+" )\n"+sylabels+" )\n"

        # Shared d[0] and pairs of y, ey
        elif self.combo_autoscript.get_index() == 4:

            # hard code the first columns
            sx  = "x  = ( d[0]"
            sy  = "y  = ( d[1]"
            sey = "ey = ( d[2]"

            # hard code the first labels
            sxlabels = "xlabels = '"  +self.ckeys[0]+"'"
            sylabels = "ylabels = ( '"+self.ckeys[1]+"'"

            # loop over any remaining columns and append.
            for n in range(1,int((len(self)-1)/2)):
                sy  += ", d["+str(2*n+1)  +"]"
                sey += ", d["+str(2*n+2)+"]"
                sylabels += ", '"+self.ckeys[2*n+1]+"'"

            return sx+" )\n"+sy+" )\n"+sey+" )\n\n"+sxlabels+"\n"+sylabels+" )\n"

        # Shared x-axis (None)
        elif self.combo_autoscript.get_index() == 5:

            # hard code the first columns
            sx = "x = ( None"
            sy = "y = ( d[0]"

            # hard code the first labels
            sxlabels = "xlabels = 'Array Index'"
            sylabels = "ylabels = ( '"+self.ckeys[0]+"'"

            # loop over any remaining columns and append.
            for n in range(1,len(self)):
                sy += ", d["+str(n)+"]"
                sylabels += ", '"+self.ckeys[n]+"'"

            return sx+" )\n"+sy+" )\n\n"+sxlabels+"\n"+sylabels+" )\n"



        else: return self.autoscript_custom()

    def autoscript_custom(self):
        """
        Overwrite this function (returning a valid script string) to redefine
        the custom autoscript.
        """
        return "To use the 'Custom Autoscript' option, you must overwrite the function 'self.autoscript_custom' with your own (which must return a valid python script string)."

    # Globals to help execute the plot script
    plot_script_globals = dict();

    def plot(self):
        """
        Updates the plot according to the script and internal data.
        """

        # If we're disabled or have no data, clear
        if not self.button_enabled.is_checked() \
        or len(self)==0:
            self._set_number_of_plots([],[])
            return self

        # if there is no script, create a default
        if not self.combo_autoscript.get_index()==0:
            self.script.set_text(self._generate_autoscript())

        ##### Try the script and make the curves / plots match
        try:

            # get globals for sin, cos etc and libraries
            g = dict(_n.__dict__, np=_n, _n=_n, numpy=_n)
            g.update(_scipy_special.__dict__, special=_scipy_special)
            g.update(dict(spinmob=_s, sm=_s, s=_s, _s=_s))

            # Pyqtgraph globals
            g.update(dict(mkPen=_pg.mkPen, mkBrush=_pg.mkBrush))

            # Object globals
            g.update(dict(d=self, x=None, y=None, ex=None, ey=None, styles=self._styles))

            # Default values
            g.update(dict(xlabels='x', ylabels='y'))

            # Other globals
            g.update(self.plot_script_globals)

            # run the script.
            exec(self.script.get_text(), g)

            # x & y should now be data arrays, lists of data arrays or Nones
            x = g['x']
            y = g['y']
            #ex = g['ex']
            ey = g['ey'] # Use spinmob._plotting_mess

            # make everything the right shape
            #x, y = _s.fun._match_data_sets(x,y)
            #ey   = _s.fun._match_error_to_data_set(y,ey)

            x = list(x)
            y = list(y)
            
            y, x = _n.histogram(y,bins = _n.linspace(min(y),max(y),(max(y)-min(y))+1))
            
            

            # make sure we have exactly the right number of plots
            self._set_number_of_plots(x,y)
            
        

            # unpink the script, since it seems to have worked
            self.script       .set_colors(None, None)
            self.button_script.set_colors(None, None)

            # Remember the style of this plot
            if self._styles: self._previous_styles = list(self._styles)
            else:            self._previous_styles = self._styles

            # Clear the error if present
            self._label_script_error.hide()

        # otherwise, look angry and don't autosave
        except Exception as e:
            self._e = e
            if _s.settings['dark_theme_qt']: self.script.set_colors(None,'#552222')
            else:                            self.script.set_colors(None,'pink')
            self.button_script.set_colors('black', 'pink')

            # Show the error
            self._label_script_error.show()
            self._label_script_error.set_text('OOP! '+ type(e).__name__ + ": '" + str(e.args[0]) + "'")
            if _s.settings['dark_theme_qt']: self._label_script_error.set_colors('pink', None)
            else:                            self._label_script_error.set_colors('red', None)

        return self

    def autosave(self):
        """
        Autosaves the currently stored data, but only if autosave is checked!
        """
        # make sure we're suppoed to
        if self.button_autosave.is_checked():

            # save the file
            self.save_file(_os.path.join(self._autosave_directory, "%04d " % (self.number_file.get_value()) + self.label_path.get_text()))

            # increment the counter
            self.number_file.increment()

        return self

    def autozoom(self, n=None):
        """
        Auto-scales the axes to fit all the data in plot index n. If n == None,
        auto-scale everyone.
        """
        if n==None:
            for p in self.plot_widgets: p.autoRange()
        else:        self.plot_widgets[n].autoRange()

        return self

    def _synchronize_controls(self):
        """
        Updates the gui based on button configs.
        """

        # whether the script is visible
        self.grid_script._widget.setVisible(self.button_script.get_value())

        # whether we should be able to edit it.
        if not self.combo_autoscript.get_index()==0: self.script.disable()
        else:                                        self.script.enable()


    def _plots_already_match_data(self, y, ey):
        """
        Checks if curves and plots all match the data and error.
        """
        # First check if the styles have changed
        if self._styles != self._previous_styles: return False

        N = len(y)

        # We should always have a curve and an error bar for each data set.
        if N != len(self._curves) or N != len(self._errors): return False

        # If we're in multiplots and the number of plots doesn't match the number of data sets
        if self.button_multi.is_checked() and N != len(self.plot_widgets): return False

        # If we're in single plot mode and the number of plots is not 1
        if not self.button_multi.is_checked() and not len(self.plot_widgets) == 1: return False

        # Make sure all the None's line up
        for n in range(N):
            if ey[n] is     None and self._errors[n] is not None: return False
            if ey[n] is not None and self._errors[n] is     None: return False

        # All good!
        return True

    def _update_legend(self, ylabels):
        """
        Updates the legend according to the list of ylabels.
        """
        if not self._legend: return

        # Clear it
        self._legend.clear()

        # Loop and append
        for i in range(len(ylabels)):

            # Only add the legend item if it's interesting
            if ylabels[i] not in [None, '', False]:
                self._legend.addItem(self._curves[i], ylabels[i])

    def _set_number_of_plots(self, x, y):
        """
        Adjusts number of plots & curves to the desired value the gui, populating
        self._curves list as needed based on y and ey.
        y and ey must be equal-length lists, but ey can have None elements.
        """
        # If we match, we're done!
        #if self._plots_already_match_data(y,ey): return

        # Otherwise, we rebuild from scratch (too difficult to track everything)

        # don't update anything until we're done
        self.grid_plot.block_signals()

        
        # clear the plots
        while len(self.plot_widgets):

            # pop the last plot widget and remove all items
            p = self.plot_widgets.pop()
            p.clear()

            # remove it from the grid so nothing is tracking it
            self.grid_plot.remove_object(p)

        # Delete the curves, too
        while len(self._curves): self._curves.pop()
        
        
        
        # Create the new curves and errors
        for i in range(1):
            

            # Default to the user-supplied self._styles, if they exist.
            if self._styles and i < len(self._styles) and self._styles[i]:
                kw = dict(stepMode = True,fillLevel =0 , fillOutline = True, brush=(0,0,255,150))
            else:
                kw = dict(stepMode = True,fillLevel =0 , fillOutline = True, brush=(0,0,255,150))

            # Append the curve @JACK
            self._curves.append(_pg.PlotDataItem(x,y,**kw))
            
            self._errors.append(None)
 
        # figure out the target number of plots
        if self.button_multi.is_checked(): n_plots = 1        # one plot per data set
        else:                              n_plots = 1 # 0 or 1 plot

        # add new plots
        for i in range(n_plots):
            self.plot_widgets.append(self.grid_plot.place_object(_pg.PlotWidget(), alignment=0))

            # Legend for single plot mode.
            if self.button_multi.is_checked(): self._legend = None
            else:                              self._legend = None

        # loop over the curves and add them to the plots
        for i in range(1):

            # Ceilinged plot_widget index (paranoid I suppose)
            l = min(i,len(self.plot_widgets)-1)

            # Always add a curve
            self.plot_widgets[l].addItem(self._curves[i])


        # loop over the ROI's and add them
        if self.ROIs is not None:

            for i in range(len(self.ROIs)):

                # get the ROIs for this plot
                ROIs = self.ROIs[i]

                if not _s.fun.is_iterable(ROIs): ROIs = [ROIs]

                # loop over the ROIs for this plot
                for ROI in ROIs:

                    # determine which plot to add the ROI to
                    m = min(i, len(self.plot_widgets)-1)

                    # add the ROI to the appropriate plot
                    if m>=0 and not ROI == None: self.plot_widgets[m].addItem(ROI)

        # show the plots
        self.grid_plot.unblock_signals()


    def _update_linked_axes(self):
        """
        Loops over the axes and links / unlinks them.
        """
        # no axes to link!
        if len(self.plot_widgets) <= 1: return

        # get the first plotItem
        a = self.plot_widgets[0].plotItem.getViewBox()

        # now loop through all the axes and link / unlink the axes
        for n in range(1,len(self.plot_widgets)):

            # Get one of the others
            b = self.plot_widgets[n].plotItem.getViewBox()

            # link the axis, but only if it isn't already
            if self.button_link_x.is_checked() and b.linkedView(b.XAxis) == None:
                b.linkView(b.XAxis, a)

            # Otherwise, unlink the guy, but only if it's linked to begin with
            elif not self.button_link_x.is_checked() and not b.linkedView(b.XAxis) == None:
                b.linkView(b.XAxis, None)        
        
        
if __name__ == '__main__':
    _egg.clear_egg_settings()
    self = histo()