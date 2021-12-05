#!/usr/bin/python

import os
import sys
import shutil
import traceback
from collections import deque

import numpy as np
import time

from mobile_insight.monitor import OfflineReplayer
from mobile_insight.analyzer.analyzer import *

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

        # source.enable_log("LTE_RRC_OTA_Packet")
        # source.enable_log("LTE_NAS_ESM_Plain_OTA_Incoming_Message")
        # source.enable_log("LTE_NAS_ESM_Plain_OTA_Outgoing_Message")
        # source.enable_log("LTE_NAS_EMM_Plain_OTA_Incoming_Message")
        # source.enable_log("LTE_NAS_EMM_Plain_OTA_Outgoing_Message")
        

    def __msg_callback(self, msg):
        if msg.type_id == "LTE_MAC_UL_Buffer_Status_Internal":
            for packet in msg.data.decode()['Subpackets']:
                # print (msg.data.decode()['timestamp'])
                

                for sample in packet['Samples']:
                    self.timer += 1

                    SFN = sample['Sub FN']
                    FN = sample['Sys FN']
                    LCIDcount = sample['Number of active LCID']
                    LCID = sample['LCIDs']
                    # Compute the latest LCID object's latency

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

                    # subframe number (SFN)  +1 -> %10 every ms
                    # frame number (FN) + 1 every 10 ms
                    # FN  SFN Bytes
                    # 99  9ms 0B
                    # 100 0ms 0B
                    # 100 1ms 50B
                    # 100 2ms 50
                    # 100 3ms 50
                    # ...
                    # 120 1ms 0B
               
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
                    # if FN < self.DCIprevFN: 
                    #     self.DCIHFN += 1
                    
                    # judge if recently add HFN
                    # 100 ms

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
                    # print(FN, SFN)


def computeULgrant(LatencyInfo, ULgrantInfo): 
    
    prevendTime = 0
    prevendFN = 0
    HFN = 0

    # find the UL grant information for each computed latency
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
                # j -= 1
                lastfound = j
                break

        grantFN = ULgrantInfo[lastfound][0]
        grantSFN = ULgrantInfo[lastfound][1]
        grantTimestamp = grantFN*10 + grantSFN
        waiting = grantTimestamp - startTime
        grant = endTime - grantTimestamp # 9 
        print("UL waiting: ", waiting, "UL grant: ", grant, "Latency: ", Latency)
        

# To use python nb-test.py /path/to/.mi2log
src = OfflineReplayer()
# src.set_input_path("./logs/latency_sample.mi2log")
src.set_input_path(sys.argv[1])
# print (sys.argv[1])

analyzer = TestAnalyzer()
analyzer.set_source(src)

src.run()

# process offline
LatencyInfo = analyzer.latencyInfo
ULgrantInfo = analyzer.DCITimeInfo
computeULgrant(LatencyInfo, ULgrantInfo)



    
