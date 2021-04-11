import serial
import pyftdi.serialext


port = pyftdi.serialext.serial_for_url('ftdi://ftdi:2232h:FT5W8DRI/1', baudrate=3000000)

while True:
	b = port.read()
	print(b)
