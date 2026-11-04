#! env/bin/python
import argparse
import os
import sys
from WaveShareUsbCanA import WaveShareUsbCanA

def hex_to_uint8_list(s: str):
    s = s.replace("0x", "").replace("0X", "").replace(" ", "")
    if len(s) % 2 != 0:
        s = s + "0"
    return [int(s[i:i+2], 16) for i in range(0, len(s), 2)]

def parse_id(id) -> int:
    if id is None:
        raise ValueError('No id set for send mode, please provide frame ID with --id or -i argument')
    int_id = int(id, 0)
    assert int_id <= ((2**29) - 1), f'id ({int_id}) too large for 29-bit extended identifier'
    return int_id

def parse_data(data) -> list[int]:
    if data is None:
        return []
    
    return hex_to_uint8_list(data)


def read_exact(stream, size):
    """Read exactly 'size' bytes from a binary stream."""
    data = bytearray()

    while len(data) < size:
        chunk = stream.read(size - len(data))

        if not chunk:
            return None

        data.extend(chunk)

    return bytes(data)


def stdin_send_loop(dongle:WaveShareUsbCanA, msg_id:int):
    stream = sys.stdin.buffer

    while True:
        # Read payload length (1 byte)
        length_byte = read_exact(stream, 1)

        if length_byte is None:
            break  # EOF

        length = length_byte[0]

        # Validate CAN payload size (Classical CAN)
        if length > 8:
            print(
                f"Invalid CAN frame length: {length}",
                file=sys.stderr
            )
            break

        # Read payload
        data = read_exact(stream, length)

        if data is None:
            print("Incomplete CAN frame received", file=sys.stderr)
            break

        try:
            dongle.send_can_frame(msg_id, list(data))

        except Exception as e:
            print(f"Error sending CAN frame: {e}", file=sys.stderr)
            break

def main():
    parser = argparse.ArgumentParser(description="Simple driver to send and receive CAN frames\
        through Waveshare USB-CAN-A device.")

    parser.add_argument('--port', '-p', required=True, help="tty port of the dongle")

    parser.add_argument('--can_baud', '-b',
        help="CAN bus baudrate: 5000, 10000, 20000, 50000, 100000, 125000,\
                200000, 250000, 400000, 500000, 800000, 1000000",
        default=500000)
    parser.add_argument('--id', '-i',
        default="0xA6",
        help="extended frame id to use, hex string")
    parser.add_argument('--data', '-d',
        help="data to be send, hex string (lsb first, padding added):\
            0xAABBC or 0xAAx0BBx0C0 sends [data0:0xAA|data1:0xBB|data2:0xC0].\
            If no message is given, data from stdin is used with the following format:\
            [1 byte: size][0 to 8 bytes: data]")
    parser.add_argument('--listen', '-l', action="store_true",
        help="listen to incoming can messages")

    args = parser.parse_args()

    dongle = WaveShareUsbCanA(args.port, args.can_baud)

    if args.listen:
        # Listen to incoming CAN messages
        pass

    elif args.data is not None:
        # Send a single frame from CLI arguments
        msg_id = parse_id(args.id)
        data = parse_data(args.data)

        dongle.send_can_frame(msg_id, data)

    else:
        # Send frames received from stdin
        msg_id = parse_id(args.id)
        stdin_send_loop(dongle, msg_id)

if __name__ == "__main__":
    main()
