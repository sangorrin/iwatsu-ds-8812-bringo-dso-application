#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2017 Daniel Sangorrin
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in all
#   copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.

# Debugging commands:
# $ picocom -c --omap crcrlf -b 115200 -f h /dev/ttyUSB0
#   DATE?

import sys
import numpy as np
from PyQt4 import QtGui, QtCore
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from window import Ui_MainWindow
import serial
import glob
import time

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
        print "command: " + cmd
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

    def acquireWave(self, channel):
        self._sendCommand('%s:TRA ON' % channel)
        self._sendCommand('WAVESRC CH%s' % channel[-1])
        reply = self._sendCommand('DTWAVE?')
        # ascii data comes in 0.1mv format
        wave = [float(item)/10000.0 for item in reply.split(',')]
        return wave

    def measure(self, channel, mode):
        self._sendCommand('DIRM A')
        self._sendCommand('MSEL %s, %s' % (channel, mode))
        time.sleep(1)
        return self._sendCommand('MSRA?')

    def Acquire(self, show_plot=True):
        self.statusBar.clearMessage()
        if not (self.ch1_checkbox.isChecked() or self.ch2_checkbox.isChecked()):
            self.statusBar.showMessage('Both channels are disabled')
            return
        else:
            self.statusBar.showMessage('Acquiring...')

        if self.longmem_checkbox.isChecked():
            self._sendCommand('MLEN LONG')
            # TODO: it should work with points = 102400 but it takes too long (try using binary data)
            self.points = 30000
        else:
            self._sendCommand('MLEN SHORT')
            self.points = 5120
        self._sendCommand('DTPOINTS ' + str(self.points))

        tdiv = float(self._sendCommand('TDIV?')) # time/div (total: 10 div)
        self.interval = (tdiv * 10) / self.points # sample_rate = 1/interval
        x = np.arange(0, self.interval * self.points, self.interval)

        if show_plot:
            self.ax1f1.clear()
            self.ax1f1.set_xlim([0, max(x)])

        if self.ch1_checkbox.isChecked():
            if self.ch1_lpfilter_checkbox.isChecked():
                self._sendCommand('C1:BWL ON')
            else:
                self._sendCommand('C1:BWL OFF')
            self.ch1_wave = self.acquireWave('C1')
            if show_plot:
                self.ax1f1.plot(x, self.ch1_wave)
            period   = self.measure('CH1', 'PERIOD')
            duty     = self.measure('CH1', 'DUTY')
            vmean    = self.measure('CH1', 'VMEAN')
            freq     = self.measure('CH1', 'FREQ')
            vrms     = self.measure('CH1', 'VRMS')
            vpp      = self.measure('CH1', 'P-P')
            tr       = self.measure('CH1', 'TR')
            tf       = self.measure('CH1', 'TF')
            pos_pw   = self.measure('CH1', '+PW')
            neg_pw   = self.measure('CH1', '-PW')
            pos_peak = self.measure('CH1', '+PEAK')
            neg_peak = self.measure('CH1', '-PEAK')
            self.ch1_measure_textedit.clear()
            self.ch1_measure_textedit.appendPlainText('Period: %s' % period)
            self.ch1_measure_textedit.appendPlainText('Duty: %s' % duty)
            self.ch1_measure_textedit.appendPlainText('Vmean: %s' % vmean)
            self.ch1_measure_textedit.appendPlainText('Freq: %s' % freq)
            self.ch1_measure_textedit.appendPlainText('Vrms: %s' % vrms)
            self.ch1_measure_textedit.appendPlainText('Vpp: %s' % vpp)
            self.ch1_measure_textedit.appendPlainText('Rise: %s' % tr)
            self.ch1_measure_textedit.appendPlainText('Fall: %s' % tf)
            self.ch1_measure_textedit.appendPlainText('+PW: %s' % pos_pw)
            self.ch1_measure_textedit.appendPlainText('-PW: %s' % neg_pw)
            self.ch1_measure_textedit.appendPlainText('+PEAK: %s' % pos_peak)
            self.ch1_measure_textedit.appendPlainText('-PEAK: %s' % neg_peak)

            #v_at_t = self._sendCommand('CURM V_AT_T')
            #self.ch1_measure_textedit.appendPlainText('Vcursor: %s' % v_at_t)

            #hcur1, hcur2 = self._sendCommand('HCUR?').split(',')
            #vcur1, vcur2 = self._sendCommand('VCUR?').split(',')


#  <-- low pass filter
# PROBE mode value (mode: AUTO, MANUAL value: 1,10,100,1000 (1:1 10:1 ...)
# AVGCNT 2..256 (requires AVERAGE mode <--

#LEVL 10~90
    #Used by: FREQ, PERIOD, +PW, -PW, and DUTY
#MCND base, 11-90, 10-89
    #base: T-B or P-P
    #Used by: TR and TF
#SKLV ch1-level>, <ch1_edge>, <ch2_level>, <ch2_edge> (RISE or FALL)
    #Used by: SKEW

        if self.ch2_checkbox.isChecked():
            if self.ch2_lpfilter_checkbox.isChecked():
                self._sendCommand('C2:BWL ON')
            else:
                self._sendCommand('C2:BWL OFF')
            self.ch2_wave = self.acquireWave('C2')
            if show_plot:
                self.ax1f1.plot(x, self.ch2_wave)
            period   = self.measure('CH2', 'PERIOD')
            duty     = self.measure('CH2', 'DUTY')
            vmean    = self.measure('CH2', 'VMEAN')
            freq     = self.measure('CH2', 'FREQ')
            vrms     = self.measure('CH2', 'VRMS')
            vpp      = self.measure('CH2', 'P-P')
            tr       = self.measure('CH2', 'TR')
            tf       = self.measure('CH2', 'TF')
            pos_pw   = self.measure('CH2', '+PW')
            neg_pw   = self.measure('CH2', '-PW')
            pos_peak = self.measure('CH2', '+PEAK')
            neg_peak = self.measure('CH2', '-PEAK')
            self.ch2_measure_textedit.clear()
            self.ch2_measure_textedit.appendPlainText('Period: %s' % period)
            self.ch2_measure_textedit.appendPlainText('Duty: %s' % duty)
            self.ch2_measure_textedit.appendPlainText('Vmean: %s' % vmean)
            self.ch2_measure_textedit.appendPlainText('Freq: %s' % freq)
            self.ch2_measure_textedit.appendPlainText('Vrms: %s' % vrms)
            self.ch2_measure_textedit.appendPlainText('Vpp: %s' % vpp)
            self.ch2_measure_textedit.appendPlainText('Rise: %s' % tr)
            self.ch2_measure_textedit.appendPlainText('Fall: %s' % tf)
            self.ch2_measure_textedit.appendPlainText('+PW: %s' % pos_pw)
            self.ch2_measure_textedit.appendPlainText('-PW: %s' % neg_pw)
            self.ch2_measure_textedit.appendPlainText('+PEAK: %s' % pos_peak)
            self.ch2_measure_textedit.appendPlainText('-PEAK: %s' % neg_peak)

        if self.ch1_checkbox.isChecked() and self.ch2_checkbox.isChecked():
            skew = self.measure('CH1', 'SKEW')
            self.ch1_measure_textedit.appendPlainText('SKEW: %s' % skew)
            # Note: should be equal
            skew = self.measure('CH2', 'SKEW')
            self.ch2_measure_textedit.appendPlainText('SKEW: %s' % skew)

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
        #self.ax1f1.set_xscale('log')
        #self.ax1f1.set_xticks([100, 1000, 10000, 100000, 1000000, 10000000])
        #self.ax1f1.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())

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

    def ch_toggled(self):
        if self.ch1_checkbox.isChecked():
            print 'ch1 enabled'
            reply = self._sendCommand('C1:TRA ON')
        else:
            print 'ch1 disabled'
            reply = self._sendCommand('C1:TRA OFF')
        if self.ch2_checkbox.isChecked():
            print 'ch2 enabled'
            reply = self._sendCommand('C2:TRA ON')
        else:
            print 'ch2 disabled'
            reply = self._sendCommand('C2:TRA OFF')

    def ch_coupling_changed(self):
        print 'ch1 coupling: ' + str(self.ch1_coupling_combo.currentText())
        self._sendCommand('C1:CPL ' + str(self.ch1_coupling_combo.currentText()))
        print 'ch2 coupling: ' + str(self.ch2_coupling_combo.currentText())
        self._sendCommand('C2:CPL ' + str(self.ch2_coupling_combo.currentText()))

    def persist_toggled(self):
        if self.persist_checkbox.isChecked():
            self._sendCommand('PERS ON')
        else:
            self._sendCommand('PERS OFF')

    def equiv_toggled(self):
        if self.equiv_checkbox.isChecked():
            self._sendCommand('EQU ON')
        else:
            self._sendCommand('EQU OFF')

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    main = Main()
    main.show()
    sys.exit(app.exec_())

