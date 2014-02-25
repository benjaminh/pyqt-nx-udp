#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# networkx graph drawing script using Qt for graphics and udpsocket for drawing signal
# created by benjaminh on Tue Feb 25 2014
# 
# Based on a reference gexf graph file, this script waits for UDP socket packet
# to draw the node and its neighbours
# 1/ Once the file is executed, a blank window is displayed
# 2/ The program waits for an UDP signal. UDPReceiver is executed in separate thread
# 3/ When a packet is received, UDP thread emits a signal with selected node as parameter
# 4/ Main GUI thread draws the received node and its neighbours in a qgraphicsscene
#
#

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import *

import os,sys, time
import socket # For UDP protocol

import networkx as nx # Module for drawing graphs

# UDPReceiver working in background
class UdpReceiver(QObject):
	def __init__(self, parent = None):
		QObject.__init__(self,parent)
		self.port = 6005
		self.initialize()

	def initialize(self):
		self.s = QUdpSocket()
		self.s.bind(QHostAddress('127.0.0.1'),self.port) # Set the IP address to listen : 127.0.0.1 for localhost
		self.s.readyRead.connect(self.receive) # Connect the readyRead function to custom receive function

	# Function receive waits for UDP datagrams and emits signal for main GUI thread
	def receive(self):
		while(self.s.hasPendingDatagrams()):
			datagram = QByteArray()
			size = self.s.pendingDatagramSize()
			data,addr,port = self.s.readDatagram(size)
			self.emit(SIGNAL("draw(PyQt_PyObject)"),data.strip()) # Send received datagram as Qt signal parameter

	def __del__(self):
		print "DESTRUCTOR"
		self.s.close()

# Node class herited from Qt QGraphicsItem class
class NodeItem(QGraphicsItem):
	def __init__(self, node, pos, radius=15, **args):
		QGraphicsItem.__init__(self, **args)
		self.pos = pos # Networkx list of graph items positions
		# Node creation
		self.node = node
		self.radius = radius
		x, y = pos[node]
		self.setPos(QPointF(x, y))

		self.setFlag(QGraphicsItem.ItemIsMovable)
		self.setFlag(QGraphicsItem.ItemIsSelectable)
		self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

	def update(self, *__args):
		self.setPos(*pos[self.node])

	def boundingRect(self):
		return QRectF(-self.radius, -self.radius, 2*self.radius, 2*self.radius)

	def paint(self, painter, style, widget=None):
		assert isinstance(painter, QPainter)
		# Color
		if self.isSelected():
			brush = QBrush(Qt.yellow)
		else:
			brush = QBrush(Qt.white)

		color = QColor(0,0,0,50)
		pen = QPen(color)

		circle_path = QPainterPath()
		circle_path.addEllipse(self.boundingRect())
		painter.fillPath(circle_path, brush)
		painter.strokePath(circle_path, pen)

		# Position for node text
		text_path = QPainterPath()
		text_path.addText(0, 0, QFont(), str(self.node))
		box = text_path.boundingRect()
		text_path.translate(-box.center())

		painter.fillPath(text_path, QBrush(Qt.black))
	
	def get_node_item(self,node_id):
		if (self.node == node_id):
			return self

# Edge class herited from QGraphicsItem Qt4 class
class EdgeItem(QGraphicsItem):
	def __init__(self, source, target, pos, **args):
		QGraphicsItem.__init__(self, **args)
		self.source = source
		self.target = target
		self.pos = pos

	def boundingRect(self):
		x0, y0 = self.pos[self.source]
		x1, y1 = self.pos[self.target]
		return QRectF(min(x0, x1), min(y0, y1), abs(x1-x0), abs(y1-y0))

	def paint(self, painter, style, widget=None):
		assert(isinstance(painter, QPainter))
		x0, y0 = self.pos[self.source]
		x1, y1 = self.pos[self.target]
		color = QColor(0,0,0,50)
		pen = QPen(color)
		painter.setPen(pen)
		painter.drawLine(x0, y0, x1, y1)

class MyWindow(QMainWindow):
	def __init__(self,parent = None):
		QMainWindow.__init__(self,parent)
		self.setFixedSize(1200,800) # To fit screen size. Didn't manage to resize the window automatically
		self.view = QGraphicsView(self)
		self.scene = QGraphicsScene()
		view = QGraphicsView(self.scene)
		self.view.setFixedSize(1200,800)

	def emitSignal(self):
		self.emit(SIGNAL("aSignal()"))
		self.show()

	# Function called by the UDP working thread when datagram is received
	def drawGraph(self,item):
		self.scene.clear()
		# Read Gexf graph file
		mygraph = nx.read_gexf("saint-sim.gexf") # Reference graph file : to be done one time only ?
		g = nx.Graph()
		g.add_edges_from(mygraph.edges())
		g.add_nodes_from(mygraph.nodes())
		pos = nx.spring_layout(g,scale=1000)
		for edge in g.edges():
			self.scene.addItem(EdgeItem(edge[0], edge[1], pos))
		for node in mygraph.nodes():
			self.scene.addItem(NodeItem(node,pos))
		# Populate empty networkx graph with selected node and neighbors
		liste = mygraph.neighbors(item)
		#Add edges based on graph
		for neighbor in liste:
			x, y = pos[neighbor]
			self.scene.itemAt(x,y).setSelected(True)
		x0,y0 = pos[item]
		self.scene.itemAt(x0,y0).setSelected(True)
		self.view.setScene(self.scene)

def main():
	qApp = QApplication(sys.argv)

	net = UdpReceiver()
	win = MyWindow()

	t = QThread()
	net.moveToThread(t)
	QObject.connect(win,SIGNAL("aSignal()"),net.receive)
	QObject.connect(net,SIGNAL("draw(PyQt_PyObject)"),win.drawGraph)

	t.start()
	win.emitSignal()
	
	sys.exit(qApp.exec_())

if __name__ == '__main__':
	main()
