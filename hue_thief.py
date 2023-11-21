import asyncio
from dataclasses import dataclass
import json
import pure_pcapy
import time
import sys
import argparse

from random import randint

import bellows
import bellows.cli.util as util
import interpanZll


DLT_IEEE802_15_4 = 195

class Prompt:
    def __init__(self):
        self.q = asyncio.Queue()
        asyncio.get_event_loop().add_reader(sys.stdin, self.got_input)

    def got_input(self):
        asyncio.ensure_future(self.q.put(sys.stdin.readline()))

    async def __call__(self, msg, end='\n', flush=False):
        print(msg, end=end, flush=flush)
        return (await self.q.get()).rstrip('\n')

async def prepare_config(device_path, baudrate):
    dev = await util.setup(device_path, baudrate)
    eui64 = await getattr(dev, 'getEui64')()
    eui64 = bellows.types.named.EmberEUI64(*eui64)

    res = await dev.mfglibStart(True)
    util.check(res[0], "Unable to start mfglib")
    return (dev, eui64)

def dump_pcap(pcap, frame):
    ts = time.time()
    ts_sec = int(ts)
    ts_usec = int((ts - ts_sec) * 1_000_000)
    hdr = pure_pcapy.Pkthdr(ts_sec, ts_usec, len(frame), len(frame))
    pcap.dump(hdr, frame)

@dataclass(eq=True, frozen=True)
class Target:
    ext_address: str
    transaction_id: int
    signal_strength: int
    channel: int
    
class ResponseHandler:
    def __init__(self, dev, pcap, channel, transaction_id, targets=None):
        self.dev = dev
        self.pcap = pcap
        self.targets = targets if targets else set()
        self.channel = channel
        self.transaction_id = transaction_id
        self.valid_responses = []
        self.invalid_responses = []
 
    def handle_incoming(self, frame_name, response):
        #print(f"Response:\n{response}")

        if frame_name != "mfglibRxHandler":
            return

        data = response[2]
        dump_pcap(self.pcap, data)

        if len(data)<10: # Not sure what this is, but not a proper response
            return

        try:
            resp = interpanZll.ScanResp.deserialize(data)[0]
        except ValueError:
            self.invalid_responses.append(response)
            return

        resp_dict = resp.__dict__
        # print(f"Response:\n{resp_dict}")
        self.valid_responses.append(resp_dict)

        if resp.transactionId != self.transaction_id: # Not for us
            return

        signal_strength = resp.rSSICorrection
        target = Target(str(resp.extSrc), self.transaction_id, signal_strength, self.channel)
        self.targets.add(target)
        frame = interpanZll.AckFrame(seq = resp.seq).serialize()
        dump_pcap(self.pcap, frame)
        asyncio.create_task(self.dev.mfglibSendPacket(frame))   


class Touchlink:

    def __init__(self, device_path, baud_rate):
        self.device_path = device_path
        self.baud_rate = baud_rate       
        self.pcap = pure_pcapy.Dumper("log.pcap", 128, DLT_IEEE802_15_4)
    
    async def create(device_path, baud_rate):
        tl = Touchlink(device_path, baud_rate)

        tl.dev, tl.eui64 = await prepare_config(device_path, baud_rate)
        return tl

    async def close(self):
        await self.dev.mfglibEnd()
        self.dev.close()

    async def scan_channel(self, channel: int) -> list[Target]:

        transaction_id = randint(0, 0xFFFFFFFF)
        handler = ResponseHandler(self.dev, self.pcap, channel, transaction_id, targets=None)
        cbid = self.dev.add_callback(handler.handle_incoming)
        
        print(f"Scanning on channel: {channel} - {type(channel)}")
        res = await self.dev.mfglibSetChannel(channel)
        util.check(res[0], "Unable to set channel")


        # https://www.nxp.com/docs/en/user-guide/JN-UG-3091.pdf section 6.8.5
        frame = interpanZll.ScanReq(
            seq = 1,
            srcPan = 0,
            extSrc = self.eui64,
            transactionId = transaction_id,
        ).serialize()
        dump_pcap(self.pcap, frame)
        res = await self.dev.mfglibSendPacket(frame)
        print(f"Sent packet: {res}")
        util.check(res[0], "Unable to send packet")

        await asyncio.sleep(1)
        self.dev.remove_callback(cbid)
        return handler.targets
        

    async def identify_bulb(self, target, transaction_id, channel):
        print(f"Sending flashing identifier packet to {target}")
        res = await self.dev.mfglibSetChannel(channel)
        util.check(res[0], "Unable to set channel")

        transaction_id = randint(0, 0xFFFFFFFF)

        frame = interpanZll.IdentifyReq(
            seq = 2,
            srcPan = 0,
            extSrc = self.eui64,
            transactionId = transaction_id,
            extDst = bellows.types.named.EmberEUI64.convert(target),
            frameControl = 0xCC21,
        ).serialize()
        dump_pcap(self.pcap, frame)
        await self.dev.mfglibSendPacket(frame)

    
    async def blink_routine(self, channels: list[int]):
        all_targets = {}
        for c in channels:
            targets = await self.scan_channel(c)
            for t in targets:
                if t not in targets:
                    all_targets[t.ext_address] = t#(t.ext_address, t.transaction_id, t.channel)

        print(f"{targets}")
        for t in targets:
            await self.identify_bulb(t.ext_address, t.transaction_id, t.channel)

    async def send_reset(self, target, transaction_id, channel):
        res = await self.dev.mfglibSetChannel(channel)
        util.check(res[0], "Unable to set channel")

        print(f"Factory resetting {target}")
        frame = interpanZll.FactoryResetReq(
            seq = 3,
            srcPan = 0,
            extSrc = self.eui64,
            transactionId = transaction_id,
            extDst = bellows.types.named.EmberEUI64.convert(target),
            frameControl = 0xCC21,
        ).serialize()
        dump_pcap(self.pcap, frame)
        await self.dev.mfglibSendPacket(frame)
        await asyncio.sleep(1)


async def steal(device_path, baudrate, scan_channel, reset_prompt=False, clean_up=True, config=None):
    if config:
        dev, eui64 = config
    else:
        dev, eui64 = await prepare_config(device_path, baudrate)
    #prompt = Prompt()
    transactions_sent = []
    transactions_received = []
    valid_responses = []
    invalid_responses = []

    channel_list = [scan_channel] if scan_channel else list(range(11, 27)).reverse()
    channel = None

    cbid = dev.add_callback(handle_incoming)


    while channel_list:
        channel = channel_list.pop()
        print("Scanning on channel",channel)
        res = await dev.mfglibSetChannel(channel)
        util.check(res[0], "Unable to set channel")

        transaction_id = randint(0, 0xFFFFFFFF)
        targets = set()

        # https://www.nxp.com/docs/en/user-guide/JN-UG-3091.pdf section 6.8.5
        frame = interpanZll.ScanReq(
            seq = 1,
            srcPan = 0,
            extSrc = eui64,
            transactionId = transaction_id,
        ).serialize()
        dump_pcap(frame)
        res = await dev.mfglibSendPacket(frame)
        transactions_sent.append(transaction_id)
        print(f"Sent packet: {res}")
        util.check(res[0], "Unable to send packet")

        await asyncio.sleep(1)

        if targets:
            print(f"Found the following targets scanning channel {channel}.\n {targets}")
        else:
            print(f"Found no targets on {channel}")

        if reset_prompt:
            while len(targets)>0:
                await handle_targets(dev, eui64, targets)

    dev.remove_callback(cbid)

    if clean_up:
        await dev.mfglibEnd()

        dev.close()

    if not reset_prompt:
        return targets

#     print(f"Saving {len(valid_responses)} valid responses")
#     with open('valid_responses.json', 'w') as fp:
#         json.dump(valid_responses, fp)
#
#     try:
#         print(f"Saving {len(invalid_responses)} invalid responses")
#         with open('invalid_responses.json', 'w') as fp:
#             json.dump(invalid_responses, fp)
#     except Exception as exc:
#         print(f"Unable to write errors: {exc}")


async def handle_targets(dev, eu164, targets):
    #prompt = Prompt()
    handled = set()
    while targets:
        (target, transaction_id, channel) = targets.pop()
        if target in handled:
            # This has already been handled on another channel
            continue
        else:
            handled.add(target)

        await identify_bulb(dev, eui64, target, transaction_id, channel)

        #answer = await prompt("Do you want to factory reset the light that just blinked? [y|n] ")
        answer = "n"

        if answer.strip().lower() == "y":
            await send_reset(dev, eui64, transaction_id, channel)


async def main(args):
    # asyncio.get_event_loop().run_until_complete(steal(args.device, args.baudrate, args.channel, reset_prompt=not args.no_reset))
    tl = await Touchlink.create(args.device, args.baudrate)
    channels = [args.channel] if args.channel else list(range(11, 27))
    await tl.blink_routine(channels)
    await tl.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Factory reset a Hue light bulb.')
    parser.add_argument('device', type=str, help='Device path, e.g., /dev/ttyUSB0')
    parser.add_argument('-b', '--baudrate', type=int, default=57600, help='Baud rate (default: 57600)')
    parser.add_argument('-c', '--channel', type=int, help='Zigbee channel (defaults to scanning 11 up to 26)')
    parser.add_argument('--no-reset', action="store_true", help='Whether to offer to reset the bulb')
    args = parser.parse_args()
    asyncio.run(main(args))

