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
        self.ch1_wave = None
        self.ch2_wave = None
        self.interval = None
        self.points = None

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

    def acquireWave(self, channel):
        self._sendCommand('%s:TRA ON' % channel)
        self._sendCommand('WAVESRC CH%s' % channel[-1])
        reply = self._sendCommand('DTWAVE?')
        # ascii data comes in 0.1mv format
        wave = [float(item)/10000.0 for item in reply.split(',')]
        return wave

    def Acquire(self, show_plot=True):
        self.statusBar.clearMessage()
        if not (self.ch1_checkbox.isChecked() or self.ch2_checkbox.isChecked()):
            self.statusBar.showMessage('Both channels are disabled')
            return
        else:
            self.statusBar.showMessage('Acquiring...')

        if self.longmem_checkbox.isChecked():
            cmd = 'MLEN LONG'
            self._sendCommand(cmd)
            # TODO: it should work with points = 102400 but it takes too long (try using binary data)
            self.points = 30000
        else:
            cmd = 'MLEN SHORT'
            self._sendCommand(cmd)
            self.points = 5120
        self._sendCommand('DTPOINTS ' + str(self.points))

        tdiv = float(self._sendCommand('TDIV?')) # time/div (total: 10 div)
        self.interval = (tdiv * 10) / self.points # sample_rate = 1/interval
        x = np.arange(0, self.interval * self.points, self.interval)

        if show_plot:
            self.ax1f1.clear()
            self.ax1f1.set_xlim([0, max(x)])

        if self.ch1_checkbox.isChecked():
            self.ch1_wave = self.acquireWave('C1')
            if show_plot:
                self.ax1f1.plot(x, self.ch1_wave)

        if self.ch2_checkbox.isChecked():
            self.ch2_wave = self.acquireWave('C2')
            if show_plot:
                self.ax1f1.plot(x, self.ch2_wave)

        if show_plot:
            self.canvas.draw()
        self.statusBar.clearMessage()
        self.statusBar.showMessage('Acquiring... FINISHED')

    def fft(self, wave):
        Fk = np.fft.fft(wave)/self.points # Fourier coefficients (divided by n)
        nu = np.fft.fftfreq(self.points, self.interval) # Natural frequencies
        Fk = np.fft.fftshift(Fk) # Shift zero freq to center
        nu = np.fft.fftshift(nu) # Shift zero freq to center
        return Fk, nu

    def rfft(self, wave):
        Fk = np.fft.rfft(wave)/self.points
        nu = np.fft.rfftfreq(self.points, self.interval)
        return Fk, nu

    def calculateFFT(self):
        self.statusBar.clearMessage()
        if not (self.ch1_checkbox.isChecked() or self.ch2_checkbox.isChecked()):
            self.statusBar.showMessage('Both channels are disabled')
            return
        else:
            self.statusBar.showMessage('Calculating FFT...')

        if any([not self.ch1_wave, not self.ch2_wave, not self.interval, not self.points]):
            self.Acquire(show_plot=False)

        self.ax1f1.clear()
        if self.ch1_checkbox.isChecked():
            Fk, nu = self.rfft(self.ch1_wave)
            self.ax1f1.plot(nu, 20*np.log10(np.absolute(Fk))) # Plot spectral power
        if self.ch2_checkbox.isChecked():
            Fk, nu = self.rfft(self.ch2_wave)
            self.ax1f1.plot(nu, 20*np.log10(np.absolute(Fk))) # Plot spectral power
        self.canvas.draw()
        self.statusBar.clearMessage()
        self.statusBar.showMessage('Calculating FFT... FINISHED')

    def aset(self):
        reply = self._sendCommand('ASET')
        self.statusBar.clearMessage()
        self.statusBar.showMessage(reply)

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

