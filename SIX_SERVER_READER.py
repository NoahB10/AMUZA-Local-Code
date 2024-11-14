import serial
import argparse
import os
from datetime import datetime

class PotentiostatReader:
    def __init__(self, com_port, baud_rate=9600, timeout=0.5, package_length=25, output_filename="out_data.txt"):
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.package_length = package_length
        self.output_filename = output_filename
        self.data_block = [b'\x00'] * package_length
        self.start_timestamp = None
        self.serial_connection = None
        self.sample_number = 1  # Initialize sample numbering

    def open_serial_connection(self):
        if self.serial_connection is None:
            self.serial_connection = serial.Serial(self.com_port, baudrate=self.baud_rate, timeout=self.timeout)

    def close_serial_connection(self):
        if self.serial_connection is not None:
            self.serial_connection.close()
            self.serial_connection = None

    def validate_data_block(self):
        header = [b'\x04', b'\x68', b'\x13', b'\x13', b'\x68']
        cks = 0
        for x in [int.from_bytes(x, 'big') for x in self.data_block[2:-4]]:
            cks = (cks + x) & 0xFF
        if (self.data_block[-5:] == header and
                self.data_block[0] == b'\x16' and
                int.from_bytes(self.data_block[1], 'big') == cks):
            return True
        return False

    def process_data_block(self):
        data_inv = [x for x in self.data_block[2:-5]]
        data_inv.reverse()
        it = iter(data_inv)
        out_data = [
            int.from_bytes(b''.join([x, next(it)]),
                           byteorder='big',
                           signed=True) for x in it]
        return out_data

    def convert_data(self, out_data):
        gain = 50 / (2**15 - 1)
        to_insert = [str(round(int(x) * gain, 3)) for x in out_data[0:6]]
        temperature = str(round(float(out_data[6]) / 16, 3)) if len(out_data) > 6 else "0"
        to_insert.append(temperature)
        return to_insert

    def get_data(self):
        self.open_serial_connection()
        accumulated_bytes = b''

        while len(accumulated_bytes) < self.package_length:
            remaining_bytes = self.package_length - len(accumulated_bytes)
            new_data = self.serial_connection.read(remaining_bytes)
            accumulated_bytes += new_data

        if accumulated_bytes:
            for byte in accumulated_bytes:
                self.data_block.insert(0, bytes([byte]))
                self.data_block.pop()

            if self.validate_data_block():
                out_data = self.process_data_block()
                return self.convert_data(out_data)
        return None

    def run(self):
        data = self.get_data()
        if data is not None:
            with open(self.output_filename, 'a') as file:
                if self.sample_number ==1:
                    # Write the "Created" line
                    created_time = datetime.now().strftime("%m/%d/%Y\t%I:%M:%S %p")
                    file.write(f"Created: {created_time}\n")

                    # Write the full header
                    header = (
                        "counter\tt[min]\t#1ch1\t#1ch2\t#1ch3\t#1ch4\t#1ch5\t#1ch6\t#1ch7\t#1ch8\t#1ch9\t#1ch10\t"
                        "#1ch11\t#1ch12\t#1ch13\t#1ch14\t#1ch15\t#1ch16\t#2ch1\t#2ch2\t#2ch3\t#2ch4\t#2ch5\t#2ch6\t"
                        "#2ch7\t#2ch8\t#2ch9\t#2ch10\t#2ch11\t#2ch12\t#2ch13\t#2ch14\t#2ch15\t#2ch16\t#3ch1\t#3ch2\t"
                        "#3ch3\t#3ch4\t#3ch5\t#3ch6\t#3ch7\t#3ch8\t#3ch9\t#3ch10\t#3ch11\t#3ch12\t#3ch13\t#3ch14\t"
                        "#3ch15\t#3ch16\t#4ch1\t#4ch2\t#4ch3\t#4ch4\t#4ch5\t#4ch6\t#4ch7\t#4ch8\t#4ch9\t#4ch10\t"
                        "#4ch11\t#4ch12\t#4ch13\t#4ch14\t#4ch15\t#4ch16\n"
                    )
                    file.write(header)
                    # Write the "Start" line
                    start_time = datetime.now().strftime("%m/%d/%Y\t%I:%M:%S %p")
                    file.write(f"Start: {start_time}\n")
                data_line = f"{self.sample_number}\t" + "\t".join(data) + "\n"
                file.write(data_line)
            self.sample_number += 1
        return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Potentiostat Data Reader")
    parser.add_argument("--com_port", type=str, required=True, help="COM port for the potentiostat")
    parser.add_argument("--baud_rate", type=int, default=9600, help="Baud rate for serial communication")
    parser.add_argument("--timeout", type=float, default=0.5, help="Timeout for serial communication")
    parser.add_argument("--package_length", type=int, default=25, help="Expected package length for data")
    parser.add_argument("--output_filename", type=str, default="out_data.txt", help="File to save the output data")

    args = parser.parse_args()
    reader = PotentiostatReader(
        com_port=args.com_port,
        baud_rate=args.baud_rate,
        timeout=args.timeout,
        package_length=args.package_length,
        output_filename=args.output_filename,
    )
    try:
        reader.run()
    except KeyboardInterrupt:
        print("Data collection stopped by user.")
    finally:
        reader.close_serial_connection()
