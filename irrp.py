#!/usr/bin/env python

# irrp.py
# 2015-12-21
# Public Domain
# 2020-12-08
# Moduled by Cartelet
"""
A utility to record and then playback IR remote control codes.

RECORD

glitch     ignore edges shorter than glitch microseconds, default 100 us
post       expect post milliseconds of silence after code, default 15 ms
pre        expect pre milliseconds of silence before code, default 200 ms
short      reject codes with less than short pulses, default 10
tolerance  consider pulses the same if within tolerance percent, default 15
no_confirm don't require a code to be repeated during record

TRANSMIT

freq       IR carrier frequency, default 38 kHz
gap        gap in milliseconds between transmitted codes, default 100 ms
"""

import time
import json
import os

import pigpio  # http://abyz.co.uk/rpi/pigpio/python.html


class IRRP:
    def __init__(self,
                 file: str,
                 freq: float = 38.0,
                 gap: int = 100,
                 glitch: int = 100,
                 pre: int = 200,
                 post: int = 15,
                 short: int = 10,
                 tolerance: int = 15,
                 verbose: bool = False,
                 no_confirm: bool = False):
        
        self.GPIO = None
        self.FILE = file              #Filename

        self.FREQ = freq              #frequency kHz

        self.GAP_MS = gap             #key gap ms
        self.GLITCH = glitch          #glitch us
        self.POST_MS = post           #postamble ms
        self.PRE_MS = pre             #preamble ms
        self.SHORT = short            #short code length
        self.TOLERANCE = tolerance    #tolerance percent

        self.VERBOSE = verbose        #Be verbose
        self.NO_CONFIRM = no_confirm  #No confirm needed

        self.POST_US = self.POST_MS * 1000
        self.PRE_US = self.PRE_MS * 1000
        self.GAP_S = self.GAP_MS / 1000.0
        self.CONFIRM = not self.NO_CONFIRM
        self.TOLER_MIN = (100 - self.TOLERANCE) / 100.0
        self.TOLER_MAX = (100 + self.TOLERANCE) / 100.0

        self.last_tick = 0
        self.in_code = False
        self.code = []
        self.fetching_code = False


    def _backup(self, f):
        """
       f -> f.bak -> f.bak1 -> f.bak2
       """
        try:
            os.rename(
                os.path.realpath(f) + ".bak1",
                os.path.realpath(f) + ".bak2")
        except:
            pass

        try:
            os.rename(
                os.path.realpath(f) + ".bak",
                os.path.realpath(f) + ".bak1")
        except:
            pass

        try:
            os.rename(os.path.realpath(f), os.path.realpath(f) + ".bak")
        except:
            pass

    def _carrier(self, gpio, frequency, micros):
        """
       Generate carrier square wave.
       """
        wf = []
        cycle = 1000.0 / frequency
        cycles = int(round(micros / cycle))
        on = int(round(cycle / 2.0))
        sofar = 0
        for c in range(cycles):
            target = int(round((c + 1) * cycle))
            sofar += on
            off = target - sofar
            sofar += off
            wf.append(pigpio.pulse(1 << gpio, 0, on))
            wf.append(pigpio.pulse(0, 1 << gpio, off))
        return wf

    def _normalise(self, c):
        """
       Typically a code will be made up of two or three distinct
       marks (carrier) and spaces (no carrier) of different lengths.

       Because of transmission and reception errors those pulses
       which should all be x micros long will have a variance around x.

       This function identifies the distinct pulses and takes the
       average of the lengths making up each distinct pulse.  Marks
       and spaces are processed separately.

       This makes the eventual generation of waves much more efficient.

       Input

         M    S   M   S   M   S   M    S   M    S   M
       9000 4500 600 540 620 560 590 1660 620 1690 615

       Distinct marks

       9000                average 9000
       600 620 590 620 615 average  609

       Distinct spaces

       4500                average 4500
       540 560             average  550
       1660 1690           average 1675

       Output

         M    S   M   S   M   S   M    S   M    S   M
       9000 4500 609 550 609 550 609 1675 609 1675 609
       """
        if self.VERBOSE:
            print("before normalise", c)
        entries = len(c)
        p = [0] * entries  # Set all entries not processed.
        for i in range(entries):
            if not p[i]:  # Not processed?
                v = c[i]
                tot = v
                similar = 1.0

                # Find all pulses with similar lengths to the start pulse.
                for j in range(i + 2, entries, 2):
                    if not p[j]:  # Unprocessed.
                        if (c[j] * self.TOLER_MIN) < v < (
                                c[j] * self.TOLER_MAX):  # Similar.
                            tot = tot + c[j]
                            similar += 1.0

                # Calculate the average pulse length.
                newv = round(tot / similar, 2)
                c[i] = newv

                # Set all similar pulses to the average value.
                for j in range(i + 2, entries, 2):
                    if not p[j]:  # Unprocessed.
                        if (c[j] * self.TOLER_MIN) < v < (
                                c[j] * self.TOLER_MAX):  # Similar.
                            c[j] = newv
                            p[j] = 1

        if self.VERBOSE:
            print("after normalise", c)

    def _compare(self, p1, p2):
        """
       Check that both recodings correspond in pulse length to within
       TOLERANCE%.  If they do average the two recordings pulse lengths.

       Input

            M    S   M   S   M   S   M    S   M    S   M
       1: 9000 4500 600 560 600 560 600 1700 600 1700 600
       2: 9020 4570 590 550 590 550 590 1640 590 1640 590

       Output

       A: 9010 4535 595 555 595 555 595 1670 595 1670 595
       """
        if len(p1) != len(p2):
            return False

        for i in range(len(p1)):
            v = p1[i] / p2[i]
            if (v < self.TOLER_MIN) or (v > self.TOLER_MAX):
                return False

        for i in range(len(p1)):
            p1[i] = int(round((p1[i] + p2[i]) / 2.0))

        if self.VERBOSE:
            print("after compare", p1)

        return True

    def _tidy_mark_space(self, records, base):

        ms = {}

        # Find all the unique marks (base=0) or spaces (base=1)
        # and count the number of times they appear,

        for rec in records:
            rl = len(records[rec])
            for i in range(base, rl, 2):
                if records[rec][i] in ms:
                    ms[records[rec][i]] += 1
                else:
                    ms[records[rec][i]] = 1

        if self.VERBOSE:
            print("t_m_s A", ms)

        v = None

        for plen in sorted(ms):

            # Now go through in order, shortest first, and collapse
            # pulses which are the same within a tolerance to the
            # same value.  The value is the weighted average of the
            # occurences.
            #
            # E.g. 500x20 550x30 600x30  1000x10 1100x10  1700x5 1750x5
            #
            # becomes 556(x80) 1050(x20) 1725(x10)
            #
            if v == None:
                e = [plen]
                v = plen
                tot = plen * ms[plen]
                similar = ms[plen]

            elif plen < (v * self.TOLER_MAX):
                e.append(plen)
                tot += (plen * ms[plen])
                similar += ms[plen]

            else:
                v = int(round(tot / float(similar)))
                # set all previous to v
                for i in e:
                    ms[i] = v
                e = [plen]
                v = plen
                tot = plen * ms[plen]
                similar = ms[plen]

        v = int(round(tot / float(similar)))
        # set all previous to v
        for i in e:
            ms[i] = v

        if self.VERBOSE:
            print("t_m_s B", ms)

        for rec in records:
            rl = len(records[rec])
            for i in range(base, rl, 2):
                records[rec][i] = ms[records[rec][i]]

    def _tidy(self, records):

        self._tidy_mark_space(records, 0)  # Marks.

        self._tidy_mark_space(records, 1)  # Spaces.

    def _end_of_code(self):
        if len(self.code) > self.SHORT:
            self._normalise(self.code)
            self.fetching_code = False
        else:
            self.code = []
            print("Short code, probably a repeat, try again")

    def _cbf(self, gpio, level, tick):

        if level != pigpio.TIMEOUT:

            edge = pigpio.tickDiff(self.last_tick, tick)
            self.last_tick = tick

            if self.fetching_code:

                if (edge > self.PRE_US) and (
                        not self.in_code):  # Start of a code.
                    self.in_code = True
                    self.pi.set_watchdog(self.GPIO,
                                         self.POST_MS)  # Start watchdog.

                elif (edge > self.POST_US) and self.in_code:  # End of a code.
                    self.in_code = False
                    self.pi.set_watchdog(self.GPIO, 0)  # Cancel watchdog.
                    self._end_of_code()

                elif self.in_code:
                    self.code.append(edge)

        else:
            self.pi.set_watchdog(self.GPIO, 0)  # Cancel watchdog.
            if self.in_code:
                self.in_code = False
                self._end_of_code()

    def Record(self, GPIO:int, ID:list, file:str="", pre:int=None, post:int=None):

        self.pi = pigpio.pi()  # Connect to Pi.

        self.GPIO = GPIO
        if file:
            FILE = file
        else:
            FILE = self.FILE
        if pre:
            self.PRE_MS = pre
            self.PRE_US = self.PRE_MS * 1000
        if post:
            self.POST_MS = post
            self.POST_US = self.POST_MS * 1000
        try:
            f = open(self.FILE, "r")
            records = json.load(f)
            f.close()
        except:
            records = {}

        self.pi.set_mode(GPIO, pigpio.INPUT)  # IR RX connected to this GPIO.

        self.pi.set_glitch_filter(GPIO, self.GLITCH)  # Ignore glitches.

        cb = self.pi.callback(GPIO, pigpio.EITHER_EDGE, self._cbf)

        # Process each id
        if isinstance(ID, str):
            ID = [ID]
        print("Recording")
        for arg in ID:
            print("Press key for '{}'".format(arg))
            self.code = []
            self.fetching_code = True
            while self.fetching_code:
                time.sleep(0.1)
            print("Okay")
            time.sleep(0.5)

            if self.CONFIRM:
                press_1 = self.code[:]
                done = False

                tries = 0
                while not done:
                    print("Press key for '{}' to confirm".format(arg))
                    self.code = []
                    self.fetching_code = True
                    while self.fetching_code:
                        time.sleep(0.1)
                    press_2 = self.code[:]
                    the_same = self._compare(press_1, press_2)
                    if the_same:
                        done = True
                        records[arg] = press_1[:]
                        print("Okay")
                        time.sleep(0.5)
                    else:
                        tries += 1
                        if tries <= 3:
                            print("No match")
                        else:
                            print("Giving up on key '{}'".format(arg))
                            done = True
                        time.sleep(0.5)
            else:  # No confirm.
                records[arg] = self.code[:]

        self.pi.set_glitch_filter(GPIO, 0)  # Cancel glitch filter.
        self.pi.set_watchdog(GPIO, 0)  # Cancel watchdog.

        self._tidy(records)

        self._backup(FILE)

        f = open(FILE, "w")
        f.write(
            json.dumps(records, sort_keys=True).replace("],", "],\n") + "\n")
        f.close()
        self.pi.stop()  # Disconnect from Pi.

    def Playback(self, GPIO:int, ID:int, file:str=""):  # Playback.

        self.pi = pigpio.pi()  # Connect to Pi.

        if file:
            FILE = file
        else:
            FILE = self.FILE
        try:
            f = open(FILE, "r")
        except:
            print("Can't open: {}".format(FILE))
            exit(0)

        records = json.load(f)

        f.close()

        self.pi.set_mode(GPIO, pigpio.OUTPUT)  # IR TX connected to this GPIO.

        self.pi.wave_add_new()

        emit_time = time.time()

        if self.VERBOSE:
            print("Playing")
        
        if isinstance(ID, str):
            ID = [ID]
        for arg in ID:
            if arg in records:

                self.code = records[arg]

                # Create wave

                marks_wid = {}
                spaces_wid = {}

                wave = [0] * len(self.code)

                for i in range(0, len(self.code)):
                    ci = self.code[i]
                    if i & 1:  # Space
                        if ci not in spaces_wid:
                            self.pi.wave_add_generic([pigpio.pulse(0, 0, ci)])
                            spaces_wid[ci] = self.pi.wave_create()
                        wave[i] = spaces_wid[ci]
                    else:  # Mark
                        if ci not in marks_wid:
                            wf = self._carrier(GPIO, self.FREQ, ci)
                            self.pi.wave_add_generic(wf)
                            marks_wid[ci] = self.pi.wave_create()
                        wave[i] = marks_wid[ci]

                delay = emit_time - time.time()

                if delay > 0.0:
                    time.sleep(delay)

                self.pi.wave_chain(wave)

                if self.VERBOSE:
                    print("key " + arg)

                while self.pi.wave_tx_busy():
                    time.sleep(0.002)

                emit_time = time.time() + self.GAP_S

                for i in marks_wid:
                    self.pi.wave_delete(marks_wid[i])

                marks_wid = {}

                for i in spaces_wid:
                    self.pi.wave_delete(spaces_wid[i])

                spaces_wid = {}
            else:
                print("Id {} not found".format(arg))

        self.pi.stop()  # Disconnect from Pi.

    def stop(self):
        if self.pi.connected:
            self.pi.stop()  # Disconnect from Pi.

