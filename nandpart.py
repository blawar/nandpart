import os
import sys
import wmi
from math import ceil
from math import floor
from zlib import crc32
from binascii import hexlify as hx, unhexlify as uhx

from PyQt5.QtWidgets import QComboBox, QMainWindow, QApplication, QWidget, QAction, QTableWidget,QTableWidgetItem,QVBoxLayout,QDesktopWidget, QTabWidget, QProgressBar, QLabel,QHBoxLayout, QLineEdit, QPushButton, QCheckBox, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot,Qt,QTimer
from PyQt5 import QtWidgets

SECTOR_COUNT_32GB = 61071360
SECTOR_COUNT_256GB = 488552715
SECTOR_END_PADDING = 1056769
	
def LBAOffset(lba):
	return lba * 512

def sizeStr(n):
	max = 1500
	suffixes = [' B', ' KB', ' MB', ' GB', ' TB']
	for s in suffixes:
		if n < 1500:
			return str(round(n, 1)) + s

		n = n / 1024

	return str(round(n, 1)) + ' PB'
	
class File:
	def __init__(self, f, offset, size):
		self.f = f
		self.i = 0
		self.offset = offset
		self.size = size
		
	def seek(self, offset):
		self.i = offset
		
	def flush(self):
		self.f.flush()
		
	def read(self, size = None, offset = None):
		if offset is not None:
			self.seek(offset)
		
		actualOffset = self.offset + self.i
		alignedOffset = floor(actualOffset / 512) * 512
		alignedOffsetEnd = ceil((actualOffset + size) / 512) * 512
		alignedSize = alignedOffsetEnd - alignedOffset
		
		self.f.seek(alignedOffset)
		
		alignedBytes = self.f.read(alignedSize)
		
		bytes = alignedBytes[actualOffset - alignedOffset:actualOffset - alignedOffset + size]
		
		self.i += len(bytes)
		
		return bytes
		
	def readInt8(self, byteorder='little', signed = False):
		return self.read(1)[0]
		
	def readInt16(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(2), byteorder=byteorder, signed=signed)
		
	def readInt32(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(4), byteorder=byteorder, signed=signed)

	def readInt48(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(6), byteorder=byteorder, signed=signed)
		
	def readInt64(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(8), byteorder=byteorder, signed=signed)

	def readInt128(self, byteorder='little', signed = False):
		return int.from_bytes(self.read(16), byteorder=byteorder, signed=signed)

	def readInt(self, size, byteorder='little', signed = False):
		return int.from_bytes(self.read(size), byteorder=byteorder, signed=signed)
		
	def write(self, value, offset = None, size = None):
		if size != None:
			value = value + '\0x00' * (size - len(value))
			
		if offset is not None:
			self.seek(offset)
			
		size = len(value)
			
		actualOffset = self.offset + self.i
		alignedOffset = floor(actualOffset / 512) * 512
		alignedOffsetEnd = ceil((actualOffset + size) / 512) * 512
		alignedSize = alignedOffsetEnd - alignedOffset
		
		self.f.seek(alignedOffset)
		
		alignedBytes = bytearray(self.f.read(alignedSize))
		alignedBytes[actualOffset - alignedOffset:actualOffset - alignedOffset + size] = value
		
		self.f.seek(alignedOffset)
		
		#print(alignedBytes)
		#raise IOError('hmm')
		#Print.info('writing to ' + hex(self.f.tell()) + ' ' + self.f.__class__.__name__)
		#Hex.dump(value)
		return self.f.write(alignedBytes)

	def writeInt8(self, value, byteorder='little', signed = False):
		return self.write(value.to_bytes(1, byteorder))
		
	def writeInt16(self, value, byteorder='little', signed = False):
		return self.write(value.to_bytes(2, byteorder))
		
	def writeInt32(self, value, byteorder='little', signed = False):
		return self.write(value.to_bytes(4, byteorder))
		
	def writeInt64(self, value, byteorder='little', signed = False):
		return self.write(value.to_bytes(8, byteorder))

	def writeInt128(self, value, byteorder='little', signed = False):
		return self.write(value.to_bytes(16, byteorder))

	def writeInt(self, value, size, byteorder='little', signed = False):
		return self.write(value.to_bytes(size, byteorder))
	
class MBRPartition(File):
	def __init__(self, f, offset):
		super(MBRPartition, self).__init__(f, offset, 0x10)
		
	def print(self):
		print('boot_indicator:\t\t%x' % self.readInt8())
		print('chs_start.head:\t\t%x' % self.readInt8())
		print('chs_start.sect:\t\t%x' % self.readInt8())
		print('chs_start.cyl:\t\t%x' % self.readInt8())
		print('system_indicator:\t%x' % self.readInt8())
		print('chs_end.head:\t\t%x' % self.readInt8())
		print('chs_end.sector:\t\t%x' % self.readInt8())
		print('chs_end.cyl:\t\t%x' % self.readInt8())
		print('sectors_before:\t\t%x' % self.readInt32())
		print('number_of_sectors:\t%x' % self.readInt32())
		
class GPTPartition(File):
	def __init__(self, f, offset, size):
		super(GPTPartition, self).__init__(f, offset, size)
		
	def type(self):
		self.seek(0x00)
		return self.read(0x10)
		
	def guid(self):
		self.seek(0x10)
		return self.read(0x10)
		
	def firstLba(self):
		self.seek(0x20)
		return self.readInt64()
		
	def lastLba(self):
		self.seek(0x28)
		return self.readInt64()
		
	def setLastLba(self, n):
		self.seek(0x28)
		return self.writeInt64(n)
		
	def attributes(self):
		self.seek(0x30)
		return self.readInt64()
		
	def name(self):
		self.seek(0x38)
		return self.read(72).decode('UTF-16LE')
		
	def print(self):
		print('name:\t\t%s' % self.name())
		print('first lba:\t\t%d' % self.firstLba())
		print('last lba:\t\t%d' % self.lastLba())
		
class GPT(File):
	def __init__(self, f, offset, size):
		super(GPT, self).__init__(f, offset, size)
		
		if self.magic() != b'EFI PART':
			raise IOError('invalid GPT magic')
			
		self.partitions = []
		
		start = ceil(self.partitionEntryOffset() / 0x10) * 0x10
		start2 = LBAOffset(2)
		partitionSize = self.partitionEntrySize()
		
		print('start %x, size = %x' % (start, partitionSize))
		print('startLba = %x' % self.partitionEntryStartLba())
		for i in range(self.partitionEntryCount() + 3):
			if i < 3:
				#self.partitions.append(GPTPartition(self.f, start + (i * partitionSize), partitionSize))
				pass
			else:
				self.partitions.append(GPTPartition(self.f, start2 + ((i-3) * partitionSize), partitionSize))
			
		
	def partitionEntryOffset(self):
		return LBAOffset(1) + self.headerSize()
		
	def magic(self):
		return self.read(8, 0)
		
	def revision(self):
		self.seek(0x08)
		return self.readInt32()
		
	def headerSize(self):
		self.seek(0x0C)
		return self.readInt32()
		
	def crc(self):
		self.seek(0x10)
		return self.readInt32()
		
	def setCrc(self):
		checksum = crc32(self.header())
		self.seek(0x10)
		return self.writeInt32(checksum)
		
	def currentLba(self):
		self.seek(0x18)
		return self.readInt64()
		
	def backupLba(self):
		self.seek(0x20)
		return self.readInt64()
		
	def firstUsableLba(self):
		self.seek(0x28)
		return self.readInt64()
		
	def lastUsableLba(self):
		self.seek(0x30)
		return self.readInt64()
		
	def diskGUID(self):
		self.seek(0x38)
		return self.read(0x10)
		
	def partitionEntryStartLba(self):
		self.seek(0x48)
		return self.readInt64()
		
	def partitionEntryCount(self):
		self.seek(0x50)
		return self.readInt32()
		
	def partitionEntrySize(self):
		self.seek(0x54)
		return self.readInt32()
		
	def partitionEntriesCrc(self):
		self.seek(0x58)
		return self.readInt32()
	
	def setPartitionEntriesCrc(self):
		checksum = crc32(self.partitionData())
		self.seek(0x58)
		return self.writeInt32(checksum)
		
	def header(self):
		buf = bytearray(self.read(self.headerSize(), 0))
		buf[0x10:0x14] = b'\x00\x00\x00\x00'
		return buf
		
	def partitionData(self):
		data = self.read(self.partitionEntryCount() * self.partitionEntrySize(), LBAOffset(1))
		return data
		
	def print(self):
		print('header size:\t\t%d' % self.headerSize())
		print('header crc:\t\t%x vs %x' % (self.crc(), crc32(self.header())))
		print('partitions:\t\t%d' % self.partitionEntryCount())
		print('partitions crc:\t\t%x vs %x' % (self.partitionEntriesCrc(), crc32(self.partitionData())))
		
		for p in self.partitions:
			p.print()
	
class MBR(File):
	def __init__(self, f, offset, size):
		super(MBR, self).__init__(f, offset, size)
		self.partitions = []
		
		
		if self.magic() != 0x55AA:
			raise IOError('Invalid MBR magic')
			
		for i in range(4):
			self.partitions.append(MBRPartition(f, 0x1BE + 0x10 * i))

	def gpt(self):
		return GPT(self.f, LBAOffset(1), LBAOffset(10))
		
	def magic(self):
		print(self.f)
		return int.from_bytes(self.read(2, 0x1FE), byteorder='big')
		
	def partitionData(self):
		return self.read(512, 0)
		
	def print(self):
		for p in self.partitions:
			p.print()
		
		
def resize():
	with open(sys.argv[1], 'rb+') as f:
		mbr = MBR(f, 0, LBAOffset(1))
		gpt = mbr.gpt()
		gpt.print()
		#mbr.gpt().partitions[13].print()
		#mbr.print()
		#mbr.seek(LBAOffset(SECTOR_COUNT_32GB-1))
		#print(mbr.read(512, LBAOffset(SECTOR_COUNT_256GB-1) - 0x400))
		#print(mbr.read(0x512, LBAOffset(2)))
		#print(mbr.read(0x512, LBAOffset(SECTOR_COUNT_256GB-33)))
	
		#print(mbr.read(512, LBAOffset(1)))
		#print(mbr.read(512, LBAOffset(SECTOR_COUNT_256GB-1)))
	
		'''
		gptData = mbr.read(512, LBAOffset(1))
		partitionData = mbr.read(0x4000, LBAOffset(2))
	

		mbr.write(gptData,  LBAOffset(SECTOR_COUNT_256GB-1))
		mbr.write(partitionData,  LBAOffset(SECTOR_COUNT_256GB-33))
	
		gpt.partitions[13].setLastLba(SECTOR_COUNT_256GB - SECTOR_END_PADDING)
	
		gpt.setPartitionEntriesCrc()
		gpt.setCrc()
		'''

	
		#with open('E:\\RAWNAND.bin', 'rb') as f2:
		#	mbr.seek(0)
		#	mbr.write(f2.read(0x800000))
	
		#mbr.flush()

def fileSize(path):
	if os.path.isfile(path):
		with open(path, 'rb') as f:
			f.seek(0,2)
			return f.tell()
	return 512

class Image(File):
	def __init__(self, path, size = None, sectorSize = 512):
		if size is None:
			size = fileSize(path)

		super(Image, self).__init__(None, 0, size)

		self.path = path
		self.size = size
		self.sectorSize = sectorSize
		self.f = None

	def __str__(self):
		return str(self.path)

	def open(self, mode = 'rb'):
		if not self.isOpen():
			self.f = open(self.path, mode)
			self.mbr = MBR(self.f, 0, LBAOffset(1))

		return self.f

	def close(self):
		if self.isOpen():
			self.mbr = None
			self.f.close()
			self.f = None

	def isOpen(self):
		return True if self.f is not None else False

class Header:
	def __init__(self, app):
		self.app = app

		self.srcSelected = 0
		self.destSelected = 0

		self.files = self.getFiles()

		self.layout = QHBoxLayout()

		self.srcLabel = QLabel("Source: ")
		self.srcLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		self.layout.addWidget(self.srcLabel)

		self.src = QComboBox()
		for f in self.files:
			self.src.addItem(str(f))

		self.src.currentIndexChanged.connect(self.onSrcChange)

		self.layout.addWidget(self.src)

		'''
		self.destLabel = QLabel("Destination: ")
		self.destLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		self.layout.addWidget(self.destLabel)

		self.dest = QComboBox()
		for f in self.files:
			self.dest.addItem(str(f))

		self.dest.currentIndexChanged.connect(self.onDestChange)

		self.layout.addWidget(self.dest)
		'''


		self.copy = QPushButton('Resize', app)
		self.copy.clicked.connect(self.onCopy)
		self.layout.addWidget(self.copy)

		self.timer = QTimer()
		self.timer.setInterval(1000)
		self.timer.timeout.connect(self.tick)
		self.timer.start()

	def getFiles(self):
		files = [Image(None, 0)]
		disks = wmi.WMI().Win32_DiskDrive(MediaType="Removable Media")
		for disk in disks:
			files.append(Image(disk.name, int(disk.size), disk.BytesPerSector))

		for f in os.listdir('.'):
			if os.path.isfile(f) and f.lower().endswith('.bin'):
				files.append(Image(f))
		return files

	def onSrcChange(self, i):
		self.srcSelected = i

		self.app.refreshTable()

	def onDestChange(self, i):
		self.destSelected = i

	def srcFile(self):
		return self.files[self.srcSelected]

	def onCopy(self):
		if not self.srcSelected:
			QMessageBox.question(self.app, 'ERROR', "Please select a source.", QMessageBox.Ok, QMessageBox.Ok)
			return

		'''
		if not self.destSelected:
			QMessageBox.question(self.app, 'ERROR', "Please select a destination.", QMessageBox.Ok, QMessageBox.Ok)
			return
		'''

		if self.app.freeSpace < 1024 * 1024 * 1024:
			QMessageBox.question(self.app, 'ERROR', "Not enough free space to increase partition size", QMessageBox.Ok, QMessageBox.Ok)
			return

		if QMessageBox.question(self.app, 'WARNING', "The destination will be overwritten, are you sure you would like to continue?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
			return

		file = self.srcFile()

		file.open('rb+')
		mbr = self.srcFile().mbr
		gpt = mbr.gpt()

		gptData = file.read(512, LBAOffset(1))
		partitionData = file.read(0x4000, LBAOffset(2))
	

		file.write(gptData, file.size - LBAOffset(1))
		file.write(partitionData, file.size - LBAOffset(33))
	
		gpt.partitions[10].setLastLba((file.size / 512) - SECTOR_END_PADDING)
	
		gpt.setPartitionEntriesCrc()
		gpt.setCrc()

		file.close()

	def onCheck(self, state):
		if state == Qt.Checked:
			Config.autolaunchBrowser = True
		else:
			Config.autolaunchBrowser = False
		Config.save()

	def updatePath(self):
		Config.paths.scan = self.textbox.text()
		Config.save()

	def tick(self):
		pass

class Progress:
	def __init__(self, app):
		self.app = app
		self.progress = QProgressBar(app)
		self.text = QLabel()
		self.speed = QLabel()
		self.text.resize(100, 40)
		self.speed.resize(100, 40)

		self.layout = QHBoxLayout()
		self.layout.addWidget(self.text)
		self.layout.addWidget(self.progress)
		self.layout.addWidget(self.speed)

		self.timer = QTimer()
		self.timer.setInterval(250)
		self.timer.timeout.connect(self.tick)
		self.timer.start()

	def resetStatus(self):
		self.progress.setValue(0)
		self.text.setText('')
		self.speed.setText('')

	def tick(self):
		'''
		try:
			self.progress.setValue(i.i / i.size * 100)
			self.text.setText(i.desc)
			self.speed.setText(formatSpeed(i.a / (time.clock() - i.ats)))
		except:
			self.resetStatus()
		'''


		if self.app.needsRefresh:
			self.app.needsRefresh = False
			self.app.refreshTable()

class App(QWidget):
	def __init__(self):
		super().__init__()
		self.setWindowIcon(QIcon('public_html/images/logo.jpg'))
		screen = QDesktopWidget().screenGeometry()
		self.title = 'NAND Part'

		self.width = 600
		self.height = 700

		self.freeSpace = 0

		self.left = self.width / 2 
		self.top = self.height / 2 
		self.setFixedSize(self.width, self.height)

		self.needsRefresh = False
		self.initUI()

	def refresh(self):
		self.needsRefresh = True
 
	def initUI(self):
		self.setWindowTitle(self.title)
		self.setGeometry(self.left, self.top, self.width, self.height)

		self.layout = QVBoxLayout()

		self.header = Header(self)
		self.layout.addLayout(self.header.layout)

		self.layout.addWidget(self.createTable())

		self.progress = Progress(self)
		self.layout.addLayout(self.progress.layout)

		self.setLayout(self.layout)
 
		self.show()

	def createTable(self):
		self.tableWidget = QTableWidget()
		self.tableWidget.setColumnCount(5)

		headers = [QTableWidgetItem("Index"), QTableWidgetItem("Label"), QTableWidgetItem("LBA Start"), QTableWidgetItem("LBA End"), QTableWidgetItem("Size")]

		i = 0
		for h in headers:
			self.tableWidget.setHorizontalHeaderItem(i, h)
			i = i + 1

		header = self.tableWidget.horizontalHeader()
		i = 0
		for h in headers:
			header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch if i == 1 else QtWidgets.QHeaderView.ResizeToContents)
			i = i + 1

		self.tableWidget.setSortingEnabled(True)

		return self.tableWidget

	def refreshTable(self):
		file = self.header.srcFile()
		file.open('rb')
		mbr = self.header.srcFile().mbr
		gpt = mbr.gpt()
		lastLba = 0
		totalLbas = file.size / 512
		print('lbs: ' + str(totalLbas))
		self.tableWidget.setRowCount(len(gpt.partitions) + 1)
		i = 0
		for p in gpt.partitions:
			lastLba = p.lastLba()
			self.tableWidget.setItem(i,0, QTableWidgetItem(str(i)))
			self.tableWidget.setItem(i,1, QTableWidgetItem(p.name()))
			self.tableWidget.setItem(i,2, QTableWidgetItem(str(p.firstLba())))
			self.tableWidget.setItem(i,3, QTableWidgetItem(str(lastLba)))
			self.tableWidget.setItem(i,4, QTableWidgetItem(str(sizeStr(LBAOffset(lastLba - p.firstLba())))))
			i = i + 1

		if totalLbas < lastLba:
			totalLbas = lastLba

		self.freeSpace = LBAOffset(totalLbas - lastLba)

		self.tableWidget.setItem(i,0, QTableWidgetItem(str(i)))
		self.tableWidget.setItem(i,1, QTableWidgetItem("Free space"))
		self.tableWidget.setItem(i,2, QTableWidgetItem(''))
		self.tableWidget.setItem(i,3, QTableWidgetItem(''))
		self.tableWidget.setItem(i,4, QTableWidgetItem(str(sizeStr(self.freeSpace))))

		self.tableWidget.setRowCount(i+1)
		file.close()


app = QApplication(sys.argv)
ex = App()

sys.exit(app.exec_())