import serial

class WaveShareUsbCanA_Speed:
    CANUSB_SPEED_1000000 = 0x01
    CANUSB_SPEED_800000  = 0x02
    CANUSB_SPEED_500000  = 0x03
    CANUSB_SPEED_400000  = 0x04
    CANUSB_SPEED_250000  = 0x05
    CANUSB_SPEED_200000  = 0x06
    CANUSB_SPEED_125000  = 0x07
    CANUSB_SPEED_100000  = 0x08
    CANUSB_SPEED_50000   = 0x09
    CANUSB_SPEED_20000   = 0x0a
    CANUSB_SPEED_10000   = 0x0b
    CANUSB_SPEED_5000    = 0x0c
    
    @staticmethod
    def code_from_value(speed:int) -> int:
        match speed:
            case 5000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_5000
            case 10000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_10000
            case 20000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_20000
            case 50000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_50000
            case 100000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_100000
            case 125000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_125000
            case 200000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_200000
            case 250000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_250000
            case 400000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_400000
            case 500000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_500000
            case 800000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_800000
            case 1000000:
                return WaveShareUsbCanA_Speed.CANUSB_SPEED_1000000
            case _:
                raise ValueError(f'can baudrate ({speed}) not supported')

class WaveShareUsbCanA_Frame:
    CANUSB_FRAME_STANDARD = 0x01
    CANUSB_FRAME_EXTENDED = 0x02

class WaveShareUsbCanA_Mode:
    CANUSB_MODE_NORMAL          = 0x00
    CANUSB_MODE_LOOPBACK        = 0x01
    CANUSB_MODE_SILENT          = 0x02
    CANUSB_MODE_LOOPBACK_SILENT = 0x03

class WaveShareUsbCanA_PayloadMode:
    CANUSB_INJECT_PAYLOAD_MODE_RANDOM      = 0x00
    CANUSB_INJECT_PAYLOAD_MODE_INCREMENTAL = 0x01
    CANUSB_INJECT_PAYLOAD_MODE_FIXED       = 0x02

class WaveShareUsbCanA_AutoResend:
    CANUSB_AUTO_RETRANSMISSION = 0x00

class WaveShareUsbCanA_ProtocolMode:
    CANUSB_PROTOCOL_FIXED    = 0x0
    CANUSB_PROTOCOL_VARIABLE = 0x12

class WaveShareUsbCanA:
    UART_BAUD = 2000000
    UART_BIT_SIZE = 8
    UART_PARITY = "N"
    UART_STOP = 1
    ser: serial.Serial

    def __init__(self, port:str = "/dev/ttyUSB0", baud:int=500000):
        self.ser = serial.Serial(port, self.UART_BAUD, self.UART_BIT_SIZE, self.UART_PARITY, self.UART_STOP)

        # Initialize the device with default parameters
        init_cmd = WaveShareUsbCanA.setting_cmd(
            WaveShareUsbCanA_Speed.code_from_value(baud),
            WaveShareUsbCanA_Frame.CANUSB_FRAME_EXTENDED,
            WaveShareUsbCanA_Mode.CANUSB_MODE_NORMAL)
        
        self.ser.write(init_cmd)

    def send_can_frame(self, id:int, data:list[int], extended_frame:bool = True):
        data_len = len(data)
        assert (data_len <= 8), f'data ({[hex(x) for x in data]}) is too long, CAN frames are only up to 8 bytes long'
    
        # Byte 1 computation
        tyep = 0xc0
        tyep |= (1 << 5) if extended_frame else (0 << 5)
        tyep |= (0 << 4) # Data frame
        tyep |= (data_len & 0x0f)

        data_cmd = [
            0xaa,                # 0 Header
            tyep,                # 1 Frame fromat, type and data len
            (id & 0xff),         # 2 ID Byte 1 (extended frame)
            (id >> 8) & 0xff,    # 3 ID Byte 2 (extended frame)
            ((id >> 16) & 0xff), # 4 ID Byte 3 (extended frame)
            ((id >> 24) & 0xff)  # 5 ID Byte 4 (extended frame)
        ]

        for b in data:
            data_cmd.append(b & 0xff)
        data_cmd.append(0x55)
        
        self.ser.write(data_cmd)


    @staticmethod
    def calculate_checksum(data):
        checksum = sum(data[2:])
        return checksum & 0xff
    
    @staticmethod
    def setting_cmd(can_speed:WaveShareUsbCanA_Speed,
                        can_frame:WaveShareUsbCanA_Frame,
                        payload_mode:WaveShareUsbCanA_PayloadMode):
        command_data = [
            0xaa,         # 0  Packet header
            0x55,         # 1  Packet header
            0x12,         # 2  Type: 0x02- fixed 20 byte protocol, 0x12- variable protocol
            can_speed,    # 3   
            can_frame,    # 4  frame mode
            0x00,         # 5  Filter ID1 #TODO check if filter ID and mask ID are working
            0x00,         # 6  Filter ID2
            0x00,         # 7  Filter ID3
            0x00,         # 8  Filter ID4
            0x00,         # 9  Mask ID1
            0x00,         # 10 Mask ID2
            0x00,         # 11 Mask ID3
            0x00,         # 12 Mask ID4
            payload_mode, # 13 CAN mode
            0x00,         # 14 automatic resend: 0x0 automatic retransmission #TODO check what does 0x01 does
            0x00,         # 15 Spare
            0x00,         # 16 Spare
            0x00,         # 17 Spare
            0x00,         # 18 Spare
                          # 19 checksum added later
        ]
        checksum = WaveShareUsbCanA.calculate_checksum(command_data)
        command_data.append(checksum)

        return command_data

