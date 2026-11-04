#! env/bin/python
import argparse
import serial.tools.list_ports
from WaveShareUsbCanA import WaveShareUsbCanA
import time

def autodetect_ch340():
    CH340_VID = 0x1A86
    ports = serial.tools.list_ports.comports()
    for p in ports:
        # CH340
        if p.vid == CH340_VID:
            return p.device
    return None

def hex_to_uint8_list(s: str):
    s = s.replace("0x", "").replace("0X", "").replace(" ", "")
    if len(s) % 2 != 0:
        s = s + "0"
    return [int(s[i:i+2], 16) for i in range(0, len(s), 2)]


def parse_id(args) -> int:
    if args.id is None:
        raise ValueError('No id set for send mode, please provide frame ID with --id or -i argument')
    int_id = int(args.id, 0)
    assert int_id <= ((2**29) - 1), f'id ({int_id}) too large for 29-bit extended identifier'
    return int_id

def parse_data(args) -> list[int]:
    if args.data is None:
        return []
    
    data = hex_to_uint8_list(args.data)
    return data

def parse_id_data(args) -> tuple[int, list[int]]:
    return parse_id(args), parse_data(args)

def parse_args(arglist = None):
    parser = argparse.ArgumentParser(description="Simple driver to send CAN frames with Waveshare\
                                      USB-CAN-A device")
    parser.add_argument('--port', '-p',
                        help="dongle serial port (COMX, /dev/ttyUSBX). If not set search for the\
                              correct device",
                        default=None)
    parser.add_argument('--id', '-i',
                        help="extended frame id to use, hex string")
    parser.add_argument('--data', '-d',
                        help="data to be send, hex string (lsb first, padding added):\
                            0xAABBC or 0xAAx0BBx0C0 sends [data0:0xAA|data1:0xBB|data2:0xC0]")
    parser.add_argument('--can_baud', '-b',
                        help="CAN bus baudrate: 5000, 10000, 20000, 50000, 100000, 125000,\
                              200000, 250000, 400000, 500000, 800000, 1000000",
                        default=500000)
    parser.add_argument('--listen', '-l',
                        help = "Set the device to listen mode, received frames are\
                            printed [ID]:[data]")
    parser.add_argument('--repeat', '-r',
                        type= int,
                        help="sends the message multiple time")
    parser.add_argument('--delay', '-ms',
                        default=200,
                        type=int,
                        help="time delay between two messages in ms")

    return parser.parse_args(arglist)

def main():
    args = parse_args()
    send_mode = True

    # Serial port:
    if args.port is None:
        port = autodetect_ch340()
        if port is None:
            raise Exception('No serial port found, provide it with --port or -p argument')
    else:
        port = args.port

    # listen or send mode
    if args.listen is None:
        # send mode
        send_mode = True
        id, data = parse_id_data(args)
    else:
        send_mode = False

    # repeat and delay
    if args.repeat is None:
        cnt = 1
        delay = 0
    else:
        cnt = args.repeat + 1
        delay = args.delay

    # Init dongle
    dongle = WaveShareUsbCanA(port, args.can_baud)
    time.sleep(0.1)

    if send_mode:
        for _ in range(0, cnt):
            dongle.send_can_frame(id, data)
            time.sleep(delay / 1000)

    if not send_mode:
        # Receive mode
        pass
    
if __name__ == "__main__":
    main()
