import serial as _serial
import numpy  as _n

class PCIT1_api():
    """
    Commands-only object for interacting with an TeachSpin PCIT1-A
    pulse counter/interval timer.
    
    Parameters
    ----------
    port='COM3' : str
        Name of the port to connect to.
    baudrate=230400 : int
        Baud rate of the connection. Must match the instrument setting.
    timeout=15 : number
        How long to wait for responses before giving up (s). 
        
    """
    def __init__(self, port='COM4', address=0, baudrate=230400, timeout=15):
        
        self.n = 0
        
        if not _serial:
            print('You need to install pyserial to use the TeachSpin PCIT1-A.')
            self.simulation_mode = True
        
        self.simulation_mode = False
        
        # If the port is "Simulation"
        if port=='Simulation': self.simulation_mode = True
        
        # If we have all the libraries, try connecting.
        if not self.simulation_mode:
            try:
                # Create the instrument and ensure the settings are correct.
                self.device = _serial.Serial(port, baudrate)
            # Something went wrong. Go into simulation mode.
            except Exception as e:
                  print('Could not open connection to "'+port+':'+'" at baudrate '+str(baudrate)+'. Entering simulation mode.')
                  print(e)
                  self.simulation_mode = True
                  self.device = None
    
    def read_line(self):
        """
        Reads a single line of data.

        Returns
        -------
        iteration : int
            Iteration number of the counter.
        count : int
            Number of counts.

        """
        if not self.simulation_mode:
            data = self.device.read_until(expected='\n\r'.encode())
            data = data.decode()
            iteration, count = [int(i) for i in data.strip('\n\r').split(',')]
            
        else:
            self.n +=1 if self.n < 65535 else  0
            iteration = self.n
            count = int(_n.rint(_n.random.normal(50, 8)))

        return iteration, count    
    def read_all_data(self):
        """
        Reads all data in the input buffer.

        Returns
        -------
        iteration_numbers : list
            List of iteration numbers of the counter.
        counts : list
            List of counts at each respective iteration.

        """
        iteration_numbers  = []
        counts   = []
        
        if not self.simulation_mode:
            while self.device.in_waiting != 0:
                iteration, n_counts = self.read_line()
                
                iteration_numbers.append(iteration)
                counts           .append(n_counts)
        else:
            for i in range(_n.random.randint(1,10)):
                iteration, n_counts = self.read_line()
                
                iteration_numbers.append(iteration)
                counts           .append(n_counts)
                
        return iteration_numbers, counts
            
        
    def disconnect(self):
        """
        Disconnects the port.
        """
        if not self.simulation_mode and self.device != None: 
            self.device.close()
            self.device = None
