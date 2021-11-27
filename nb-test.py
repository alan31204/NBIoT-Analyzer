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

    def set_source(self, source):
        Analyzer.set_source(self, source)

        source.enable_log("LTE_PHY_PUSCH_Tx_Report")
        source.enable_log("LTE_MAC_UL_Buffer_Status_Internal")
        # source.enable_log("LTE_MAC_DL_Buffer_Status_Internal")
        source.enable_log("LTE_NB1_ML1_GM_DCI_Info")
        # source.enable_log("LTE_NB1_ML1_GM_PDSCH_STAT_Ind")

        # source.enable_log("LTE_RRC_OTA_Packet")
        # source.enable_log("LTE_NAS_ESM_Plain_OTA_Incoming_Message")
        # source.enable_log("LTE_NAS_ESM_Plain_OTA_Outgoing_Message")
        # source.enable_log("LTE_NAS_EMM_Plain_OTA_Incoming_Message")
        # source.enable_log("LTE_NAS_EMM_Plain_OTA_Outgoing_Message")
        

    def __msg_callback(self, msg):
        if msg.type_id == "LTE_MAC_UL_Buffer_Status_Internal":
            for packet in msg.data.decode()['Subpackets']:
                # print (msg.data.decode()['timestamp'])
                
                prevSFN = 0
                prevFN = 0
                

                for sample in packet['Samples']:
                    self.timer += 1

                    SFN = sample['Sub FN']
                    FN = sample['Sys FN']
                    LCIDcount = sample['Number of active LCID']
                    LCID = sample['LCIDs']
                    # Compute the latest LCID object's latency
                    
                    # print(sample)

                    for i in range(LCIDcount): 
                        Byte = LCID[i]['Total Bytes']

                    if self.prevByte < Byte: 
                        self.bufferqueue.append([Byte - self.prevByte, Byte - self.prevByte, self.timer])

                        # print( Byte, prevByte)
                    
                    if self.prevByte >= Byte and self.prevByte > 0: 
                        # data is sending out
                        outdata = self.prevByte - Byte


                        while len(self.bufferqueue) > 0 and self.bufferqueue[0][0] <= outdata: 
                            Latency = self.timer - self.bufferqueue[0][2]
                            # Latency = time.perf_counter() - self.bufferqueue[0][1]
                            # print(self.timer, self.bufferqueue[0])
                            print("Latency is: ", Latency, "with size of ", self.bufferqueue[0][0])
                            self.latencyInfo.append(Latency)
                            outdata -= self.bufferqueue[0][0]
                            self.bufferqueue.popleft()
                            

                        if outdata > 0: 
                            self.bufferqueue[0][0] -= outdata

                        # if self.bufferqueue[0][0] > outdata: 
                        #     Latency = self.timer - self.bufferqueue[0][1]
                        #     # print("Latency info: ", Latency)
                        #     self.bufferqueue[0][0] -= outdata

                    
                    self.prevByte = Byte
                        

                    # if prevSFN != SFN: 
                    #     prevSFN = SFN
                    # if prevFN != FN: 
                    #     prevFN = FN
                    # print("SFN: ", SFN)
                    # print("FN: ", FN)
                    # print("LCID: ", LCID)
                    # print("LCount", LCIDcount)

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
                    UL_grant = True # grant and the time data is sent out
                elif record['DL Grant Present'] == 'True':
                    DL_grant = True
                

                if UL_grant: 
                    FN = record['NPDCCH Timing SFN']
                    SFN = record['NPDCCH Timing Sub FN']
                    self.latencyInfo
                    print(FN, SFN)

                # print(record)
                if DL_grant: 
                    FN = record['NPDCCH Timing SFN']
                    SFN = record['NPDCCH Timing Sub FN']
                    # print(FN, SFN)



# To use python nb-test.py /path/to/.mi2log
src = OfflineReplayer()
# src.set_input_path("./logs/latency_sample.mi2log")
src.set_input_path(sys.argv[1])
# print (sys.argv[1])

analyzer = TestAnalyzer()
analyzer.set_source(src)

src.run()