import sys
import numpy as np
from PyQt4 import QtGui, QtCore
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from window import Ui_MainWindow
import serial
import glob

class Main(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(Main, self).__init__()
        self.setupUi(self)

        # add a figure to the canvas with a navigation toolbar
        self.fig = Figure()
        self.ax1f1 = self.fig.add_subplot(111)
        self.ax1f1.set_autoscalex_on(False)
        self.canvas = FigureCanvas(self.fig)
        self.matplot_vlayout.addWidget(self.canvas)
        self.toolbar = NavigationToolbar(self.canvas,
                self.matplot_widget, coordinates=True)
        self.matplot_vlayout.addWidget(self.toolbar)

        # prepare the serial port combo
        serial_list = sorted(glob.glob('/dev/ttyUSB*'), key = lambda x: int(x[11:]))
        serial_list += sorted(glob.glob('/dev/ttyACM*'), key = lambda x: int(x[11:]))
        serial_list += sorted(glob.glob('/dev/ttyS*'), key = lambda x: int(x[9:]))[:5]
        self.serial_combo.addItems(serial_list)
        self.serial_port = None

    def check_serial_port(self):
        if not self.serial_port:
            port = str(self.serial_combo.currentText())
            try:
                self.serial_port = serial.Serial(port,
                                                baudrate=115200,
                                                parity=serial.PARITY_NONE,
                                                stopbits=serial.STOPBITS_ONE,
                                                rtscts=True,
                                                timeout=30.0)
                self.serial_combo.setEnabled(False)
            except serial.SerialException:
                raise Exception("Couln't open the serial port " + port)

    # \n  ASCII Linefeed (LF)
    # \r    ASCII Carriage Return (CR)
    def readlineCR(self):
        rv = ""
        while True:
            ch = self.serial_port.read()
            if ch == '\x06':
                return 'ack'
            rv += ch
            if ch=='\n':
                return rv

    def _sendCommand(self, cmd):
        try:
            self.check_serial_port()
        except Exception as e:
            self.statusBar.clearMessage()
            self.statusBar.showMessage(str(e))
            return
        self.serial_port.write(str(cmd) + '\r\n')
        reply = self.readlineCR()
        if reply != 'ack':
            self.statusBar.clearMessage()
            self.statusBar.showMessage('nack')
            return
        if str(cmd)[-1] == '?':
            reply = self.readlineCR()
        return reply.strip('\r\n')

    #def sendCommand(self):
        #cmd = self.cmd_entry.text()
        #self._sendCommand(cmd)
        #self.cmd_entry.clear()
        #self.cmd_reply_text.appendPlainText(cmd)
        #self.cmd_reply_text.appendPlainText(reply)

    #def sendQuery(self, cmd):
        #reply = self._sendCommand(cmd)
        #self.cmd_reply_text.appendPlainText(cmd)
        #self.cmd_reply_text.appendPlainText(reply)

    def acquireWave(self):
        self.statusBar.clearMessage()
        self.statusBar.showMessage('Acquiring...')
        if self.longmem_checkbox.isChecked():
            cmd = 'MLEN LONG'
            self._sendCommand(cmd)
            # points = 102400
            points = 30000
        else:
            cmd = 'MLEN SHORT'
            self._sendCommand(cmd)
            points = 5120
        self._sendCommand('DTPOINTS ' + str(points))
        print points

        self.ax1f1.clear()
        tdiv = float(self._sendCommand('TDIV?'))
        sample_rate = points / (tdiv * 10) # the osc has 10 divisions
        interval = (tdiv * 10) / points

        # TODO: use a common routine
        if self.ch1_checkbox.isChecked():
            self._sendCommand('C1:TRA ON')
            vdiv1 = float(self._sendCommand('C1:VDIV?'))
            self._sendCommand('WAVESRC CH1')
            reply = self._sendCommand('DTWAVE?')
            # ascii data comes in 0.1mv format
            wave1 = [float(item)/10000.0 for item in reply.split(',')]
            x = np.arange(0, interval*len(wave1), interval)
            #self.ax1f1.set_xlim([0,max(x)])
            #self.ax1f1.plot(x, wave1)

        if self.ch2_checkbox.isChecked():
            self._sendCommand('C2:TRA ON')
            vdiv1 = float(self._sendCommand('C2:VDIV?'))
            self._sendCommand('WAVESRC CH2')
            reply = self._sendCommand('DTWAVE?')
            # ascii data comes in 0.1mv format
            wave2 = [float(item)/10000.0 for item in reply.split(',')]
            x = np.arange(0, interval*len(wave2), interval)
            #self.ax1f1.set_xlim([0,max(x)])
            #self.ax1f1.plot(x, wave2)

        #n = len(wave1[0:63])
        #d = 1./sample_rate
        #fs = np.fft.rfftfreq(n, d)
        #print fs
        #hs = np.fft.rfft(wave1[0:63])
        from numpy import fft
        print 'rate: ' + str(sample_rate)
        Fk = fft.fft(wave1)/points # Fourier coefficients (divided by n)
        nu = fft.fftfreq(points, 1/sample_rate) # Natural frequencies
        Fk = fft.fftshift(Fk) # Shift zero freq to center
        nu = fft.fftshift(nu) # Shift zero freq to center

        #hs = np.asanyarray(hs)
        #fs = np.asanyarray(fs)
        #self.ax1f1.set_xlim([0,max(fs)])
        self.ax1f1.set_autoscaley_on(True)
        self.ax1f1.set_autoscalex_on(True)

        #i = None if high is None else find_index(high, self.fs)
        #thinkplot.plot(self.fs[:i], self.hs[:i], **options)
        self.ax1f1.plot(nu, np.absolute(Fk)**2) # Plot spectral power
        #self.ax1f1.plot(fs, hs)
        #self.ax1f1.plot(nu, np.absolute(np.real(Fk))) # Plot Cosine terms
        self.canvas.draw()
        self.statusBar.clearMessage()
        self.statusBar.showMessage('Acquiring... FINISHED')

    def calculateFFT(self):
        print 'calc FFT'

    def ch1_toggled(self):
        if self.ch1_checkbox.isChecked():
            print 'ch1 enabled'
            reply = self._sendCommand('C1:TRA ON')
        else:
            print 'ch1 disabled'
            reply = self._sendCommand('C1:TRA OFF')

    def ch2_toggled(self):
        if self.ch2_checkbox.isChecked():
            print 'ch2 enabled'
            reply = self._sendCommand('C2:TRA ON')
        else:
            print 'ch2 disabled'
            reply = self._sendCommand('C2:TRA OFF')

    def ch1_coupling_changed(self):
        print 'ch1 coupling: ' + str(self.ch1_coupling_combo.currentText())
        self._sendCommand('C1:CPL ' + str(self.ch1_coupling_combo.currentText()))

    def ch2_coupling_changed(self):
        print 'ch2 coupling: ' + str(self.ch2_coupling_combo.currentText())
        self._sendCommand('C2:CPL ' + str(self.ch2_coupling_combo.currentText()))

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    main = Main()
    main.show()
    sys.exit(app.exec_())

