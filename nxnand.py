import os
import sys
from math import ceil
from math import floor
from zlib import crc32
from binascii import hexlify as hx, unhexlify as uhx

SECTOR_COUNT_32GB = 61071360
SECTOR_COUNT_256GB = 488552715
SECTOR_END_PADDING = 1056769

if len(sys.argv) != 2:
	print('usage:  resize.py file')
	exit(0)
	
def LBAOffset(lba):
	return lba * 512
	
class File:
	def __init__(self, f, offset, size):
		self.f = f
		self.i = 0
		self.offset = offset
		self.size = size
		
	def seek(self, offset):
		self.i = offset
		#self.f.seek(self.offset + offset)
		
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
		
		#print('actualOffset = %d, alignedOffset = %d, size = %d, bytes read = %d, alignedSize = %d' % (actualOffset, alignedOffset, size, len(alignedBytes), alignedSize))
		#print(bytes)
		
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
				self.partitions.append(GPTPartition(self.f, start + (i * partitionSize), partitionSize))
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
	
	gptData = mbr.read(512, LBAOffset(1))
	partitionData = mbr.read(0x4000, LBAOffset(2))
	

	mbr.write(gptData,  LBAOffset(SECTOR_COUNT_256GB-1))
	mbr.write(partitionData,  LBAOffset(SECTOR_COUNT_256GB-33))
	
	gpt.partitions[13].setLastLba(SECTOR_COUNT_256GB - SECTOR_END_PADDING)
	
	gpt.setPartitionEntriesCrc()
	gpt.setCrc()

	
	#with open('E:\\RAWNAND.bin', 'rb') as f2:
	#	mbr.seek(0)
	#	mbr.write(f2.read(0x800000))
	
	#mbr.flush()
	