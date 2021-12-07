#!/usr/bin/python
# Filename: online-analysis-example.py
import os
import sys
import shutil
import traceback
from collections import deque

import numpy as np
import time

# Import MobileInsight modules
from mobile_insight.analyzer import *
from mobile_insight.monitor import OnlineMonitor


class TestAnalyzer(Analyzer):
    def __init__(self):
        Analyzer.__init__(self)
        self.add_source_callback(self.__msg_callback)
        self.bufferqueue = deque()
        self.timer = 0
        self.prevByte = 0 # setup for no possibility
        self.latencyInfo = []
        self.currLatencyCount = 0
        self.DCITimeInfo = []

        self.HFN = 0 # Hyper FN clock
        self.prevFN = 0
        self.recentupdateTime = 0

    def set_source(self, source):
        Analyzer.set_source(self, source)

        source.enable_log("LTE_PHY_PUSCH_Tx_Report")
        source.enable_log("LTE_MAC_UL_Buffer_Status_Internal")
        source.enable_log("LTE_NB1_ML1_GM_DCI_Info")

    def __msg_callback(self, msg):
        if msg.type_id == "LTE_MAC_UL_Buffer_Status_Internal":
            for packet in msg.data.decode()['Subpackets']:
                for sample in packet['Samples']:
                    self.timer += 1

                    SFN = sample['Sub FN']
                    FN = sample['Sys FN']
                    LCIDcount = sample['Number of active LCID']
                    LCID = sample['LCIDs']

                    # update on hyper FN
                    if FN < self.prevFN:
                        self.HFN += 1
                        self.recentupdateTime = msg.data.decode()['timestamp']

                    for i in range(LCIDcount): 
                        Byte = LCID[i]['Total Bytes']

                    if self.prevByte < Byte: 
                        self.bufferqueue.append([Byte - self.prevByte, Byte - self.prevByte, self.timer])
                    
                    if self.prevByte >= Byte and self.prevByte > 0: 
                        # data is sending out
                        outdata = self.prevByte - Byte


                        # data sent out and one buffer is cleared
                        while len(self.bufferqueue) > 0 and self.bufferqueue[0][0] <= outdata: 
                            Latency = self.timer - self.bufferqueue[0][2]
                            
                            # correct timestamp for FN and SFN info here
                            self.latencyInfo.append([Latency, self.bufferqueue[0][0], FN, SFN, self.HFN])
                            
                            # store latency, data size, finished time
                            outdata -= self.bufferqueue[0][0]
                            self.bufferqueue.popleft()
                            
                        # when data are sent out but buffer not yet empty
                        if outdata > 0: 
                            self.bufferqueue[0][0] -= outdata
                    self.prevByte = Byte
                    self.prevFN = FN
               
        if msg.type_id == "LTE_NB1_ML1_GM_DCI_Info":
            # print(msg.data.decode())

            for record in msg.data.decode()['Records']:
                # print(record)
                UL_grant = False
                DL_grant = False
                
                if record['UL Grant Present'] == 'True': 
                    UL_grant = True # grant and when data is sent out
                elif record['DL Grant Present'] == 'True':
                    DL_grant = True

                if UL_grant: 
                    FN = record['NPDCCH Timing SFN']
                    SFN = record['NPDCCH Timing Sub FN']
                    HFN = 0

                    diff = msg.data.decode()['timestamp'] - self.recentupdateTime
                    if diff.total_seconds() < 0.1: # recent update of HFN trigger
                        if FN > 950: # try 
                            HFN = self.HFN + 1
                        else: 
                            HFN = self.HFN
                    else: 
                        if FN < 10:
                            HFN = self.HFN - 1
                        else: 
                            HFN = self.HFN

                    self.DCITimeInfo.append([FN,SFN, HFN])
                    
                if DL_grant: 
                    FN = record['NPDCCH Timing SFN']
                    SFN = record['NPDCCH Timing Sub FN']


def computeULgrant(LatencyInfo, ULgrantInfo):  
    prevendTime = 0
    prevendFN = 0
    HFN = 0
    # find the UL grant information for each computed latency
    print("Waiting Grant  Latency  Size")
    for i in range(len(LatencyInfo)):

        Latency = LatencyInfo[i][0]
        size = LatencyInfo[i][1]
        endFN = LatencyInfo[i][2]
        endSFN = LatencyInfo[i][3]
        # HFN = LatencyInfo[i][4]
        endTime = endFN*10 + endSFN # + HFN * 10240

        startTime = endTime - Latency
        # startTemp = startTime - HFN * 10240
        # startFN = startTemp // 10
        # startSFN = startTemp % 10

        lastfound = 0
        grant_gap = 9 # proper grant gap information

        # closest one UL grant before endTime
        for j in range(lastfound, len(ULgrantInfo)): 
            newTime = ULgrantInfo[j][0]*10 + ULgrantInfo[j][1] 
            if newTime + grant_gap == endTime: # look for closest grant to end time
                lastfound = j
                break

        grantFN = ULgrantInfo[lastfound][0]
        grantSFN = ULgrantInfo[lastfound][1]
        grantTimestamp = grantFN*10 + grantSFN
        waiting = grantTimestamp - startTime
        grant = endTime - grantTimestamp # 9 
        print(waiting, "\t",  grant, "\t", Latency, "\t", size)

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("Error: please specify physical port name and baudrate.")
        print((__file__, "SERIAL_PORT_NAME BAUNRATE"))
        sys.exit(1)

    # Initialize a 3G/4G monitor
    src = OnlineMonitor()
    src.set_serial_port(sys.argv[1])  # the serial port to collect the traces: 
    src.set_baudrate(int(sys.argv[2]))  # the baudrate of the port: 115200

    # Enable 3G/4G RRC (radio resource control) monitoring
    src.enable_log("LTE_MAC_UL_Buffer_Status_Internal")
    src.enable_log("LTE_NB1_ML1_GM_DCI_Info")

    # 4G RRC analyzer
    test_analyzer = TestAnalyzer()
    test_analyzer.set_source(src)  # bind with the monitor

    # Start the monitoring
    src.run()
    LatencyInfo = analyzer.latencyInfo
    ULgrantInfo = analyzer.DCITimeInfo
    computeULgrant(LatencyInfo, ULgrantInfo)
