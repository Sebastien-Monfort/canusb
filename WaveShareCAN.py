import serial
import time
from typing import Optional
from dataclasses import dataclass, field

class CANBaudrate:
    BAUD_1000000 = 0x01
    BAUD_800000 = 0x02
    BAUD_500000 = 0x03
    BAUD_400000 = 0x04
    BAUD_250000 = 0x05
    BAUD_200000 = 0x06
    BAUD_125000 = 0x07
    BAUD_100000 = 0x08
    BAUD_50000 = 0x09
    BAUD_20000 = 0x0A
    BAUD_10000 = 0x0B
    BAUD_5000 = 0x0C

    _CODES = {
        1000000: BAUD_1000000,
        800000:  BAUD_800000,
        500000:  BAUD_500000,
        400000:  BAUD_400000,
        250000:  BAUD_250000,
        200000:  BAUD_200000,
        125000:  BAUD_125000,
        100000:  BAUD_100000,
        50000:   BAUD_50000,
        20000:   BAUD_20000,
        10000:   BAUD_10000,
        5000:    BAUD_5000,
    }

    @staticmethod
    def code_from_value(speed: int) -> int:
        try:
            return CANBaudrate._CODES[speed]
        except KeyError:
            raise ValueError(f"can baudrate ({speed}) not supported") from None

class Frame:
    STANDARD = 0x01
    EXTENDED = 0x02

class CANMode:
    NORMAL = 0x00
    SILENT = 0x01
    LOOPBACK = 0x02
    LOOPBACK_SILENT = 0x03

@dataclass
class CANMessage:
    can_id: int
    data: bytearray = b""
    extended: bool = False
    remote: bool = False
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        kind = "EXT" if self.extended else "STD"
        rtr = " RTR" if self.remote else ""
        return f"[{kind}{rtr}] id:0x{self.can_id:X} data:{self.data.hex(' ')}"

class Dongle:
    UART_BAUD = 2000000
    UART_BYTE_SIZE = 8
    UART_PARITY = "N"
    UART_STOP = 1

    VARIABLE_PROTOCOL = 0x12 # 0x02 for fixed length

    def __init__(self, port: str, can_baud: int = 500000, frame_type: int = Frame.EXTENDED):

        self.can_baud = can_baud
        self.frame_type = frame_type
        self.auto_retransmit = False
        self.mask_id = 0
        self.filter_id = 0
        self.mode = CANMode.NORMAL

        self._rx_buff = bytearray()

        if frame_type not in (Frame.STANDARD, Frame.EXTENDED):
            raise ValueError("frame_type must be Frame.FRAME_STANDARD or Frame.FRAME_EXTENDED")

        # Initialize the serial port
        self.ser = serial.Serial(
                    port,
                    baudrate=self.UART_BAUD,
                    bytesize=self.UART_BYTE_SIZE,
                    parity=self.UART_PARITY,
                    stopbits=self.UART_STOP,
                    timeout=0.1)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        # Initialize the dongle
        config_frame_data = self.config_frame()
        print(config_frame_data)
        self.ser.write(config_frame_data)
        self.ser.flush()
        time.sleep(0.1)

    def config_frame(self) -> bytearray:
        f = bytearray(20)
        f[0] = 0xAA
        f[1] = 0x55
        f[2] = self.VARIABLE_PROTOCOL
        f[3] = CANBaudrate.code_from_value(self.can_baud)
        f[4] = self.frame_type
        # Filter / mask IDs. 0 = accept everything. The wiki says "high byte
        # first" but frame IDs are little-endian; if you use a real filter and
        # it misbehaves, try swapping the byte order here.
        f[5:9] = (self.filter_id & 0xFFFFFFFF).to_bytes(4, "little")
        f[9:13] = (self.mask_id & 0xFFFFFFFF).to_bytes(4, "little")
        f[13] = self.mode
        f[14] = 0x00 if self.auto_retransmit else 0x01
        # bytes 15..18 are reserved (0x00)
        f[19] = sum(f[2:19]) & 0xFF
        return bytes(f)
    
    def encode(self, can_id:int, data:bytearray):
        if len(data) > 8:
            raise ValueError("CAN data is limited to 8 bytes")
        
        max_id = 0x1FFFFFFF if (self.frame_type == Frame.EXTENDED) else 0x7FF
        if not 0 <= can_id <= max_id:
            raise ValueError(f"can_id 0x{can_id:X} out of range")
        
        dlc = len(data)

        # Variable lengt protocol:

        type_frame = (0x20 if (self.frame_type == Frame.EXTENDED) else 0)
        msg_remote = 0 # 0-> data frame 0x10 -> remote frame
        t = 0xC0 | type_frame | msg_remote | dlc
    
        id_len = 4 if (self.frame_type == Frame.EXTENDED) else 2
    
        return bytes([0xAA, t]) + can_id.to_bytes(id_len, "little") + bytes(data) + b"\x55"


    def send(self, can_id:int, data:bytearray) -> None:
        bin_msg = self.encode(can_id, data)
        self.ser.write(bin_msg)
        self.ser.flush()
    
    def read(self) -> Optional[bytearray]:
        """Return the next CAN message, or None if nothing arrives within timeout."""
        while True:
            msg = self._parse_variable()
            if msg is not None:
                return msg

            chunk = self.ser.read(max(1, self.ser.in_waiting))
            if not chunk:
                return None
            self._rx_buff.extend(chunk)

    def _parse_variable(self) -> Optional[CANMessage]:
        buf = self._rx_buff

        while True:

            i = buf.find(0xAA)
            if i < 0:
                buf.clear()
                return None
            
            del buf[:i]
            if len(buf) < 2:
                return None
            
            t = buf[1]
            if (t & 0xC0) != 0xC0 or (t & 0x0F) > 8: # not a data/remote frame header
                del buf[0]
                continue

            extended = bool(t & 0x20)
            remote = bool(t & 0x10)

            dlc = t & 0x0F
            id_len = 4 if extended else 2
            total = 2 + id_len + dlc + 1

            if len(buf) < total:
                return None
            
            if buf[total - 1] != 0x55: # bad end code -> resync
                del buf[0]
                continue

            can_id = int.from_bytes(buf[2:2 + id_len], "little")
            data = bytes(buf[2 + id_len:2 + id_len + dlc])
            del buf[:total]
            return CANMessage(can_id, data, extended, remote)
